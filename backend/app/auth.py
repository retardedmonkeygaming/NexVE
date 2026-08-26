from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import secrets
try:
    import pyotp
except ImportError:
    pyotp = None
from .database import SessionLocal
from .models.user import User, Session as UserSession

SESSION_DURATION_HOURS = 24


def create_session(user_id: int) -> str:
    db = SessionLocal()
    try:
        token = secrets.token_urlsafe(32)
        session = UserSession(
            token=token,
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)
        )
        db.add(session)
        db.commit()
        return token
    finally:
        db.close()


def get_current_user(request: Request) -> dict | None:
    token = request.cookies.get("nexve_session")
    if not token:
        return None

    db = SessionLocal()
    try:
        session = db.query(UserSession).filter(
            UserSession.token == token,
            UserSession.expires_at > datetime.utcnow()
        ).first()

        if not session:
            return None

        user = db.query(User).filter(User.id == session.user_id).first()
        if not user or not user.is_active:
            return None

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "totp_enabled": user.totp_enabled
        }
    finally:
        db.close()


def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def destroy_session(token: str):
    db = SessionLocal()
    try:
        db.query(UserSession).filter(UserSession.token == token).delete()
        db.commit()
    finally:
        db.close()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code with ±1 window tolerance."""
    if pyotp is None:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_totp_secret() -> str:
    if pyotp is None:
        raise RuntimeError("pyotp is not installed")
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str, issuer: str = "NexVE") -> str:
    if pyotp is None:
        raise RuntimeError("pyotp is not installed")
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)
