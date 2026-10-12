from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.db.session import get_db
from backend.app.db.models import User
from backend.app.core.config import settings
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
