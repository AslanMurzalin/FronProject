import os
import tempfile
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, get_db
from backend.app.db.models import User, Session as UserSession, Upload, Job, Report
from backend.app.core.config import settings

@pytest.fixture
def test_client_and_db(tmp_path):
    db_path = str(tmp_path / "test_account.db")
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

    yield client, TestingSessionLocal, tmp_path

    app.dependency_overrides.clear()
    test_engine.dispose()

def test_delete_account_unauthenticated(test_client_and_db):
    client, _, _ = test_client_and_db
    resp = client.delete("/api/account")
    assert resp.status_code == 401
    assert "Not authenticated" in resp.json()["detail"]

def test_delete_account_full_teardown(test_client_and_db):
    client, TestingSessionLocal, tmp_path = test_client_and_db

    # 1. Register and login
    reg_resp = client.post(
        "/api/auth/register",
        json={"email": "delete_me@example.com", "password": "SafePassword123!"},
    )
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["id"]

    login_resp = client.post(
        "/api/auth/login",
        json={"email": "delete_me@example.com", "password": "SafePassword123!"},
    )
    assert login_resp.status_code == 200

    # 2. Setup user scratch files and associated database records
    db = TestingSessionLocal()
    user = db.query(User).filter_by(id=user_id).first()

    # Create dummy scratch files in temp directory
    scratch_dir = tmp_path / "scratch_demos" / "upload_123"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch_file = scratch_dir / "match.dem"
    scratch_file.write_text("dummy demo binary content")
    decompressed_file = scratch_dir / "match_decompressed.dem"
    decompressed_file.write_text("dummy decompressed content")

    assert scratch_file.exists()
    assert decompressed_file.exists()

    upload = Upload(
        user_id=user.id,
        original_filename="match.dem.zst",
        scratch_path=str(scratch_file),
        decompressed_path=str(decompressed_file),
        file_size_bytes=1000,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    job = Job(
        user_id=user.id,
        upload_id=upload.id,
        selected_steam_id="76561198000000001",
        app_version="0.1.0",
        status="processing",
        stage="timelines",
        heartbeat_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    report = Report(
        job_id=job.id,
        user_id=user.id,
        match_name="Mirage Match",
        player_nickname="UserToDelete",
        player_steam_id="76561198000000001",
        baiting_score=30,
        confidence="high",
        sub_signals="{}",
        evidence_timeline="[]",
        skipped_rounds="[]",
        config_snapshot="{}",
        app_version="0.1.0",
        weights_version="1.0.0",
        map_version="1.0.0",
    )
    db.add(report)
    db.commit()

    # Verify presence before deletion
    assert db.query(User).filter_by(id=user_id).count() == 1
    assert db.query(Upload).filter_by(user_id=user_id).count() == 1
    assert db.query(Job).filter_by(user_id=user_id).count() == 1
    assert db.query(Report).filter_by(user_id=user_id).count() == 1
    db.close()

    # 3. Call DELETE /api/account
    del_resp = client.delete("/api/account")
    assert del_resp.status_code == 200
    assert "deleted successfully" in del_resp.json()["detail"]

    # 4. Verify scratch files were unlinked from disk
    assert not scratch_file.exists()
    assert not decompressed_file.exists()

    # 5. Verify database records are cascade-deleted
    db = TestingSessionLocal()
    assert db.query(User).filter_by(id=user_id).count() == 0
    assert db.query(UserSession).filter_by(user_id=user_id).count() == 0
    assert db.query(Upload).filter_by(user_id=user_id).count() == 0
    assert db.query(Job).filter_by(user_id=user_id).count() == 0
    assert db.query(Report).filter_by(user_id=user_id).count() == 0
    db.close()

    # 6. Verify subsequent requests with old cookie return 401
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 401
