from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import User, Upload
from backend.app.core.config import settings
from backend.app.core.limiter import limiter
from backend.app.api.deps import get_current_user, verify_csrf_origin, check_user_quotas

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

@router.post("", dependencies=[Depends(verify_csrf_origin)])
@limiter.limit(settings.UPLOAD_RATE_LIMIT)
def upload_demo(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initiate or receive demo upload with rate limiting and quota verification.
    """
    # Enforce concurrent upload limit & daily analysis quota
    check_user_quotas(current_user.id, db)

    # For Task 6 quota check / initial stub before streaming upload in Task 8:
    upload = Upload(
        user_id=current_user.id,
        original_filename="uploaded_match.dem",
        file_size_bytes=1024,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.UPLOAD_TTL_SECONDS),
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    return {
        "upload_id": upload.id,
        "message": "Upload accepted",
        "expires_at": upload.expires_at.isoformat(),
    }
