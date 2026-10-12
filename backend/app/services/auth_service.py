from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.app.db.models import User, Session as UserSession
from backend.app.core.security import hash_password, verify_password, generate_session_token, hash_session_token
from backend.app.core.config import settings

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email.strip().lower())
    return db.execute(stmt).scalar_one_or_none()

def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    stmt = select(User).where(User.id == user_id)
    return db.execute(stmt).scalar_one_or_none()

def create_user(db: Session, email: str, password: str) -> User:
    email_clean = email.strip().lower()
    existing = get_user_by_email(db, email_clean)
    if existing:
        raise ValueError("User with this email already exists")

    hashed_pw = hash_password(password)
    user = User(email=email_clean, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_session(db: Session, user_id: str) -> Tuple[str, datetime]:
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    expires_at = utc_now() + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)

    session_row = UserSession(
        id=token_hash,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(session_row)
    db.commit()
    return raw_token, expires_at

def get_user_by_session_token(db: Session, raw_token: str) -> Optional[User]:
    if not raw_token:
        return None
    token_hash = hash_session_token(raw_token)
    stmt = select(UserSession).where(UserSession.id == token_hash)
    session_row = db.execute(stmt).scalar_one_or_none()
    if not session_row:
        return None

    # Check expiration
    now = utc_now()
    # Handle timezone-naive datetime comparison if stored as naive
    sess_exp = session_row.expires_at
    if sess_exp.tzinfo is None:
        sess_exp = sess_exp.replace(tzinfo=timezone.utc)

    if sess_exp < now:
        # Expired: revoke
        db.delete(session_row)
        db.commit()
        return None

    return session_row.user

def revoke_session(db: Session, raw_token: str) -> bool:
    if not raw_token:
        return False
    token_hash = hash_session_token(raw_token)
    stmt = delete(UserSession).where(UserSession.id == token_hash)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount > 0

def purge_expired_sessions(db: Session) -> int:
    now = utc_now()
    stmt = delete(UserSession).where(UserSession.expires_at < now)
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
