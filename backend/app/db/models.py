import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.base import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    # Cascades: deleting a user deletes all their sessions, uploads, jobs, and reports
    sessions: Mapped[List["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    uploads: Mapped[List["Upload"]] = relationship(
        "Upload", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    jobs: Mapped[List["Job"]] = relationship(
        "Job", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 Token Hash
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="sessions")


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    scratch_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    decompressed_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    match_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    map_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cached_roster: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="uploads")
    jobs: Mapped[List["Job"]] = relationship(
        "Job", back_populates="upload", cascade="all, delete-orphan", passive_deletes=True
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    upload_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("uploads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    match_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    selected_steam_id: Mapped[str] = mapped_column(String(32), nullable=False)
    player_nickname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failing_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="jobs")
    upload: Mapped["Upload"] = relationship("Upload", back_populates="jobs")
    report: Mapped[Optional["Report"]] = relationship(
        "Report", back_populates="job", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    match_name: Mapped[str] = mapped_column(String(255), nullable=False)
    player_nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    player_steam_id: Mapped[str] = mapped_column(String(32), nullable=False)
    baiting_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sub_signals: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    evidence_timeline: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    skipped_rounds: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    config_snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    weights_version: Mapped[str] = mapped_column(String(32), nullable=False)
    map_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="reports")
    job: Mapped["Job"] = relationship("Job", back_populates="report")
