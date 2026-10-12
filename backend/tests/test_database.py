import os
import tempfile
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.session import create_db_engine, engine as default_engine
from backend.app.db.models import User, Session as UserSession, Upload, Job, Report

@pytest.fixture
def temp_db():
    """Provides a fresh isolated SQLite database with WAL and FK pragmas for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    test_engine = create_db_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()

    yield session, test_engine

    session.close()
    test_engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)
    # Remove any WAL and SHM files
    for ext in ["-wal", "-shm"]:
        wal_file = db_path + ext
        if os.path.exists(wal_file):
            os.unlink(wal_file)

def test_wal_pragma_and_foreign_keys_configured(temp_db):
    session, test_engine = temp_db
    with test_engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        assert journal_mode.lower() == "wal"

        busy_timeout = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        assert busy_timeout == 5000

        foreign_keys = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert foreign_keys == 1

def test_create_all_tables_in_var_app_db():
    Base.metadata.create_all(bind=default_engine)
    inspector = inspect(default_engine)
    tables = inspector.get_table_names()
    expected_tables = ["users", "sessions", "uploads", "jobs", "reports"]
    for t in expected_tables:
        assert t in tables, f"Expected table {t} missing from database"

def test_foreign_key_enforcement(temp_db):
    session, _ = temp_db
    orphan_session = UserSession(
        id="hash_nonexistent_user",
        user_id="nonexistent-user-id",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(orphan_session)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

def test_user_cascade_delete(temp_db):
    session, _ = temp_db
    # 1. Create User
    user = User(email="player@example.com", hashed_password="argon2id_mock_hash")
    session.add(user)
    session.commit()
    session.refresh(user)

    # 2. Create Session
    user_session = UserSession(
        id="session_token_hash_1",
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    # 3. Create Upload
    upload = Upload(
        user_id=user.id,
        original_filename="match.dem",
        file_size_bytes=1024000,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add_all([user_session, upload])
    session.commit()
    session.refresh(upload)

    # 4. Create Job
    job = Job(
        user_id=user.id,
        upload_id=upload.id,
        selected_steam_id="76561198000000001",
        app_version="0.1.0",
        status="pending",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # 5. Create Report
    report = Report(
        job_id=job.id,
        user_id=user.id,
        match_name="Mirage vs Liquid",
        player_nickname="s1mple",
        player_steam_id="76561198000000001",
        baiting_score=42,
        confidence="medium",
        sub_signals="{}",
        evidence_timeline="[]",
        skipped_rounds="[]",
        config_snapshot="{}",
        app_version="0.1.0",
        weights_version="1.0.0",
        map_version="1.0.0",
    )
    session.add(report)
    session.commit()

    # Verify everything exists
    assert session.query(User).count() == 1
    assert session.query(UserSession).count() == 1
    assert session.query(Upload).count() == 1
    assert session.query(Job).count() == 1
    assert session.query(Report).count() == 1

    # Delete User -> must cascade delete all children
    session.delete(user)
    session.commit()

    assert session.query(User).count() == 0
    assert session.query(UserSession).count() == 0
    assert session.query(Upload).count() == 0
    assert session.query(Job).count() == 0
    assert session.query(Report).count() == 0

def test_job_cascade_delete(temp_db):
    session, _ = temp_db
    user = User(email="job_tester@example.com", hashed_password="argon2id_mock_hash")
    session.add(user)
    session.commit()

    upload = Upload(
        user_id=user.id,
        original_filename="match.dem",
        file_size_bytes=500000,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    session.add(upload)
    session.commit()

    job = Job(
        user_id=user.id,
        upload_id=upload.id,
        selected_steam_id="76561198000000002",
        app_version="0.1.0",
        status="processing",
        stage="parsing",
        heartbeat_at=datetime.now(timezone.utc),
    )
    session.add(job)
    session.commit()

    report = Report(
        job_id=job.id,
        user_id=user.id,
        match_name="Mirage Match",
        player_nickname="ZywOo",
        player_steam_id="76561198000000002",
        baiting_score=25,
        confidence="high",
        sub_signals="{}",
        evidence_timeline="[]",
        skipped_rounds="[]",
        config_snapshot="{}",
        app_version="0.1.0",
        weights_version="1.0.0",
        map_version="1.0.0",
    )
    session.add(report)
    session.commit()

    assert session.query(Job).count() == 1
    assert session.query(Report).count() == 1

    # Delete Job -> cascades to Report
    session.delete(job)
    session.commit()

    assert session.query(Job).count() == 0
    assert session.query(Report).count() == 0
    # User and Upload remain
    assert session.query(User).count() == 1
    assert session.query(Upload).count() == 1
