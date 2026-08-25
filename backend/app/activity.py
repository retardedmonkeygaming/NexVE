from fastapi import Request
from .database import SessionLocal
from .models.activity import ActivityLog


def log_activity(request: Request, user: dict, action: str, target_type: str, target_id: str = None, details: str = None):
    """Log an activity to the database."""
    db = SessionLocal()
    try:
        entry = ActivityLog(
            user_id=user.get("id") if user else None,
            username=user.get("username") if user else "system",
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            details=details,
            ip_address=request.client.host if request.client else None,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
