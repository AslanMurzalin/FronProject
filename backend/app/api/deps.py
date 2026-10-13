from datetime import datetime, timedelta, timezone
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.db.session import get_db
from backend.app.db.models import User, Upload, Job
from backend.app.core.config import settings
from backend.app.core.limiter import get_client_ip
from backend.app.services.auth_service import get_user_by_session_token

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = get_user_by_session_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return user

def verify_csrf_origin(request: Request):
    """
    Validates Origin or Referer header on state-changing requests
    to protect against Cross-Site Request Forgery (CSRF).
    """
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        origin = request.headers.get("origin")
        sec_fetch_site = request.headers.get("sec-fetch-site")

        # Sec-Fetch-Site defense
        if sec_fetch_site and sec_fetch_site == "cross-site":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-site requests forbidden",
            )

        # Origin check if present
        if origin and origin not in settings.ALLOWED_ORIGINS:
            # Allow same-origin localhost variations in test/dev
            if not any(origin.startswith(allowed) for allowed in settings.ALLOWED_ORIGINS):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid origin header",
                )


def check_user_quotas(user_id: str, db: Session, raise_exception: bool = True) -> Optional[dict]:
    """
    Validates user quotas before allowing a new demo upload or analysis:
    1. Concurrent upload limit: at most CONCURRENT_UPLOAD_LIMIT active uploads
       (uploads created within UPLOAD_TTL_SECONDS without completed/failed jobs, or jobs in pending/processing).
    2. Daily analysis quota: at most DAILY_ANALYSIS_QUOTA completed analyses in rolling 24 hours.
    """
    now = datetime.now(timezone.utc)

    # 1. Check daily analysis quota (JOBS completed within rolling 24h)
    day_ago = now - timedelta(hours=24)
    completed_jobs = (
        db.query(Job)
        .filter(
            Job.user_id == user_id,
            Job.status == "completed",
            Job.completed_at >= day_ago,
        )
        .count()
    )
    if completed_jobs >= settings.DAILY_ANALYSIS_QUOTA:
        detail = "DAILY_QUOTA_EXCEEDED"
        if raise_exception:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
            )
        return {"error_code": detail, "detail": detail}

    # 2. Check concurrent upload limit
    # Active jobs: pending or processing
    active_jobs = (
        db.query(Job)
        .filter(
            Job.user_id == user_id,
            Job.status.in_(["pending", "processing"]),
        )
        .count()
    )

    # Unanalyzed uploads: uploads created within TTL that have no jobs yet
    ttl_cutoff = now - timedelta(seconds=settings.UPLOAD_TTL_SECONDS)
    unanalyzed_uploads = (
        db.query(Upload)
        .filter(
            Upload.user_id == user_id,
            Upload.created_at >= ttl_cutoff,
            ~Upload.jobs.any(),
        )
        .count()
    )

    total_active = active_jobs + unanalyzed_uploads
    if total_active >= settings.CONCURRENT_UPLOAD_LIMIT:
        detail = "CONCURRENT_UPLOAD_LIMIT"
        if raise_exception:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
            )
        return {"error_code": detail, "detail": detail}

    return None

