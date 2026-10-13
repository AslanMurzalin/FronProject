import os
import tempfile
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, get_db
from backend.app.db.models import User, Upload, Job
from backend.app.core.config import settings
from backend.app.core.limiter import limiter, get_client_ip
from backend.app.api.deps import check_user_quotas

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()

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

def create_authenticated_user(client, email="quota_test@test.com", password="Password123!"):
    reg_resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["id"]

    login_resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    return user_id

def test_check_user_quotas_helper(test_client_and_db):
    client, TestingSessionLocal = test_client_and_db
    user_id = create_authenticated_user(client, email="helper_test@test.com")
    db = TestingSessionLocal()

    # 1. No uploads or jobs -> passes
    assert check_user_quotas(user_id, db, raise_exception=False) is None

    # 2. Add 1 active upload
    now = datetime.now(timezone.utc)
    upload = Upload(
        user_id=user_id,
        original_filename="match.dem",
        file_size_bytes=1000,
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db.add(upload)
    db.commit()

    # Should report CONCURRENT_UPLOAD_LIMIT
    res = check_user_quotas(user_id, db, raise_exception=False)
    assert res is not None
    assert res["error_code"] == "CONCURRENT_UPLOAD_LIMIT"

    # With raise_exception=True, should raise HTTPException
    with pytest.raises(Exception) as exc_info:
        check_user_quotas(user_id, db, raise_exception=True)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "CONCURRENT_UPLOAD_LIMIT"

    # Remove upload and add 10 completed jobs
    db.delete(upload)
    db.commit()

    # Daily analysis quota: 10 completed jobs in last 24h
    dummy_upload = Upload(
        user_id=user_id,
        original_filename="dummy.dem",
        file_size_bytes=500,
        created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
    )
    db.add(dummy_upload)
    db.commit()

    for i in range(10):
        job = Job(
            user_id=user_id,
            upload_id=dummy_upload.id,
            selected_steam_id="76561198000000000",
            app_version="0.1.0",
            status="completed",
            created_at=now - timedelta(hours=1),
            completed_at=now - timedelta(minutes=10 * i),
        )
        db.add(job)
    db.commit()

    # Should report DAILY_QUOTA_EXCEEDED
    res_daily = check_user_quotas(user_id, db, raise_exception=False)
    assert res_daily is not None
    assert res_daily["error_code"] == "DAILY_QUOTA_EXCEEDED"

    with pytest.raises(Exception) as exc_info2:
        check_user_quotas(user_id, db, raise_exception=True)
    assert exc_info2.value.status_code == 429
    assert exc_info2.value.detail == "DAILY_QUOTA_EXCEEDED"

    db.close()

def test_second_concurrent_upload_rejected_while_first_is_active(test_client_and_db):
    client, _ = test_client_and_db
    create_authenticated_user(client, email="concurrent@test.com")

    # First upload succeeds
    r1 = client.post("/api/uploads")
    assert r1.status_code == 200
    assert "upload_id" in r1.json()

    # Second upload attempt rejected with HTTP 429 CONCURRENT_UPLOAD_LIMIT
    r2 = client.post("/api/uploads")
    assert r2.status_code == 429
    assert r2.json()["detail"] == "CONCURRENT_UPLOAD_LIMIT"

def test_eleventh_analysis_attempt_rejected_when_ten_completed_in_24h(test_client_and_db):
    client, TestingSessionLocal = test_client_and_db
    user_id = create_authenticated_user(client, email="daily_quota@test.com")
    db = TestingSessionLocal()

    now = datetime.now(timezone.utc)
    upload = Upload(
        user_id=user_id,
        original_filename="past.dem",
        file_size_bytes=100,
        created_at=now - timedelta(hours=5),
        expires_at=now - timedelta(hours=4),
    )
    db.add(upload)
    db.commit()

    for i in range(10):
        job = Job(
            user_id=user_id,
            upload_id=upload.id,
            selected_steam_id="76561198000000000",
            app_version="0.1.0",
            status="completed",
            created_at=now - timedelta(hours=3),
            completed_at=now - timedelta(minutes=5 * i),
        )
        db.add(job)
    db.commit()
    db.close()

    # 11th analysis / upload attempt rejected with HTTP 429 DAILY_QUOTA_EXCEEDED
    resp = client.post("/api/uploads")
    assert resp.status_code == 429
    assert resp.json()["detail"] == "DAILY_QUOTA_EXCEEDED"

def test_ip_rate_limit_triggered_after_5_rapid_requests(test_client_and_db):
    client, TestingSessionLocal = test_client_and_db
    user_id = create_authenticated_user(client, email="rate_limit@test.com")

    # To trigger IP rate limit without hitting user concurrent upload limit,
    # we delete the upload from DB after each request so user quota stays 0 active.
    db = TestingSessionLocal()

    for i in range(5):
        resp = client.post("/api/uploads")
        assert resp.status_code == 200, f"Request {i+1} failed with {resp.status_code}: {resp.text}"
        # Clear uploads so concurrent limit is not triggered on next request
        db.query(Upload).filter(Upload.user_id == user_id).delete()
        db.commit()

    # 6th rapid request from the same IP should be blocked by slowapi
    r6 = client.post("/api/uploads")
    assert r6.status_code == 429
    assert r6.json()["detail"] == "RATE_LIMIT_EXCEEDED"
    db.close()

def test_client_ip_extraction_behind_trusted_x_forwarded_for(test_client_and_db):
    client, TestingSessionLocal = test_client_and_db
    user_id = create_authenticated_user(client, email="proxy_test@test.com")
    db = TestingSessionLocal()

    headers_ip1 = {"X-Forwarded-For": "203.0.113.195"}
    for i in range(5):
        resp = client.post("/api/uploads", headers=headers_ip1)
        assert resp.status_code == 200
        db.query(Upload).filter(Upload.user_id == user_id).delete()
        db.commit()

    # 6th request from IP 203.0.113.195 blocked
    r_blocked = client.post("/api/uploads", headers=headers_ip1)
    assert r_blocked.status_code == 429
    assert r_blocked.json()["detail"] == "RATE_LIMIT_EXCEEDED"

    # Request from different IP 198.51.100.10 through trusted proxy should succeed
    headers_ip2 = {"X-Forwarded-For": "198.51.100.10"}
    r_fresh = client.post("/api/uploads", headers=headers_ip2)
    assert r_fresh.status_code == 200
    db.close()
