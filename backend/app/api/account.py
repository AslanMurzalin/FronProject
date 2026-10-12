import os
import shutil
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.db.models import User, Upload, Job
from backend.app.core.config import settings
from backend.app.api.deps import get_current_user, verify_csrf_origin

router = APIRouter(prefix="/api/account", tags=["account"])

def safe_unlink(path: str | None):
    if path and os.path.exists(path):
        try:
            if os.path.isfile(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass

@router.delete("", status_code=status.HTTP_200_OK)
def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _csrf: None = Depends(verify_csrf_origin),
):
    # 1. Cancel user's pending/processing jobs
    active_jobs = db.execute(
        select(Job).where(Job.user_id == current_user.id, Job.status.in_(["pending", "processing"]))
    ).scalars().all()
    for job in active_jobs:
        job.status = "failed"
        job.error_message = "Job cancelled due to account deletion"
    db.commit()

    # 2. Unlink all user scratch demo files and directories
    user_uploads = db.execute(
        select(Upload).where(Upload.user_id == current_user.id)
    ).scalars().all()
    for upload in user_uploads:
        safe_unlink(upload.scratch_path)
        safe_unlink(upload.decompressed_path)
        # Check scratch directory for upload id
        upload_dir = os.path.join(settings.SCRATCH_DIR, str(upload.id))
        safe_unlink(upload_dir)

    # 3. Permanently delete User from DB (cascades to all sessions, uploads, jobs, reports)
    db.delete(current_user)
    db.commit()

    # 4. Clear auth cookie
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        secure=settings.SESSION_COOKIE_SECURE,
    )

    return {"detail": "Account and all associated resources deleted successfully"}
