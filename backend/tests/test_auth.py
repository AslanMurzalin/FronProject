import os
import tempfile
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, get_db
from backend.app.db.models import User, Session as UserSession
from backend.app.services.auth_service import purge_expired_sessions
from backend.app.core.config import settings

@pytest.fixture
def test_client_and_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    test_engine = create_db_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, base_url="http://localhost:5173")

    yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    test_engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)
    for ext in ["-wal", "-shm"]:
        wal = db_path + ext
        if os.path.exists(wal):
            os.unlink(wal)

def test_register_success(test_client_and_db):
    client, _ = test_client_and_db
    resp = client.post(
        "/api/auth/register",
        json={"email": "pro_player@faceit.com", "password": "StrongPassword123!"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "pro_player@faceit.com"
    assert "id" in data
    assert "created_at" in data

def test_register_duplicate_email_rejected(test_client_and_db):
    client, _ = test_client_and_db
    resp1 = client.post(
        "/api/auth/register",
        json={"email": "duplicate@test.com", "password": "Password123!"},
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/auth/register",
        json={"email": "duplicate@test.com", "password": "Password123!"},
    )
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]

def test_register_invalid_email_and_weak_password(test_client_and_db):
    client, _ = test_client_and_db
    # Invalid email
    r1 = client.post(
        "/api/auth/register",
        json={"email": "invalid-email-no-at", "password": "ValidPassword123"},
    )
    assert r1.status_code == 422

    # Weak/short password (< 8 chars)
    r2 = client.post(
        "/api/auth/register",
        json={"email": "good@test.com", "password": "short"},
    )
    assert r2.status_code == 422

def test_login_invalid_credentials(test_client_and_db):
    client, _ = test_client_and_db
    # Register first
    client.post(
        "/api/auth/register",
        json={"email": "login_test@test.com", "password": "CorrectPassword1"},
    )

    # Wrong password
    resp = client.post(
        "/api/auth/login",
        json={"email": "login_test@test.com", "password": "WrongPassword1"},
    )
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]

    # Nonexistent user
    resp2 = client.post(
        "/api/auth/login",
        json={"email": "nobody@test.com", "password": "SomePassword1"},
    )
    assert resp2.status_code == 401

def test_login_success_sets_httponly_cookie_and_persists_hash(test_client_and_db):
    client, TestingSessionLocal = test_client_and_db
    client.post(
        "/api/auth/register",
        json={"email": "session_user@test.com", "password": "Password1234"},
    )

    resp = client.post(
        "/api/auth/login",
        json={"email": "session_user@test.com", "password": "Password1234"},
    )
    assert resp.status_code == 200
    assert settings.SESSION_COOKIE_NAME in resp.cookies

    # Verify cookie attributes
    cookie_header = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header or "httponly" in cookie_header.lower()
    assert "SameSite=lax" in cookie_header or "samesite=lax" in cookie_header.lower()

    # Verify session is hashed in DB
    db = TestingSessionLocal()
    sessions = db.query(UserSession).all()
    assert len(sessions) == 1
    # Hash is SHA-256 (64 hex chars)
    assert len(sessions[0].id) == 64
    db.close()

def test_get_current_user_me_flow(test_client_and_db):
    client, _ = test_client_and_db
    # Unauthenticated /me -> 401
    unauth_resp = client.get("/api/auth/me")
    assert unauth_resp.status_code == 401

    # Login
    client.post(
        "/api/auth/register",
        json={"email": "me_user@test.com", "password": "Password1234"},
    )
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "me_user@test.com", "password": "Password1234"},
    )
    assert login_resp.status_code == 200

    # /me with cookie
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "me_user@test.com"

def test_logout_revokes_session_and_clears_cookie(test_client_and_db):
    client, TestingSessionLocal = test_client_and_db
    client.post(
        "/api/auth/register",
        json={"email": "logout_test@test.com", "password": "Password1234"},
    )
    client.post(
        "/api/auth/login",
        json={"email": "logout_test@test.com", "password": "Password1234"},
    )

    # Verify active
    assert client.get("/api/auth/me").status_code == 200

    # Logout
    logout_resp = client.post("/api/auth/logout")
    assert logout_resp.status_code == 200

    # DB session must be revoked
    db = TestingSessionLocal()
    assert db.query(UserSession).count() == 0
    db.close()

    # Subsequent /me must fail with 401
    assert client.get("/api/auth/me").status_code == 401

def test_expired_session_rejection_and_purge(test_client_and_db):
    client, TestingSessionLocal = test_client_and_db
    client.post(
        "/api/auth/register",
        json={"email": "expire_test@test.com", "password": "Password1234"},
    )
    client.post(
        "/api/auth/login",
        json={"email": "expire_test@test.com", "password": "Password1234"},
    )

    # Manually expire session in DB
    db = TestingSessionLocal()
    sess = db.query(UserSession).first()
    sess.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    db.close()

    # /me must be rejected with 401
    assert client.get("/api/auth/me").status_code == 401

    # Test purge utility
    db = TestingSessionLocal()
    # Add another already expired session for the same user
    user_id = db.query(User).first().id
    db.add(UserSession(id="expired_hash_2", user_id=user_id, expires_at=datetime.now(timezone.utc) - timedelta(days=2)))
    db.commit()
    purged = purge_expired_sessions(db)
    assert purged >= 1
    db.close()
