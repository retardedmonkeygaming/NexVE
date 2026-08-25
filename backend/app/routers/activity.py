from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from ..database import SessionLocal
from ..models.activity import ActivityLog
from ..auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_logs(request: Request, limit: int = 100, offset: int = 0):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        logs = db.query(ActivityLog).order_by(ActivityLog.id.desc()).offset(offset).limit(limit).all()
        total = db.query(ActivityLog).count()
        return JSONResponse({
            "logs": [
                {
                    "id": l.id,
                    "username": l.username,
                    "action": l.action,
                    "target_type": l.target_type,
                    "target_id": l.target_id,
                    "details": l.details,
                    "ip_address": l.ip_address,
                    "created_at": l.created_at.isoformat() if l.created_at else None,
                }
                for l in logs
            ],
            "total": total,
        })
    finally:
        db.close()
