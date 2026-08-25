from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime, timedelta
from ..database import SessionLocal
from ..models.user import User, ApiToken
from ..auth import get_current_user
import secrets
import hashlib

router = APIRouter()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.get("/")
async def list_tokens(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        tokens = db.query(ApiToken).filter(ApiToken.user_id == user["id"]).all()
        return JSONResponse(content={"tokens": [
            {
                "id": t.id,
                "name": t.name,
                "permissions": t.permissions,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "last_used": t.last_used.isoformat() if t.last_used else None,
                "enabled": t.enabled,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tokens
        ]})
    finally:
        db.close()


@router.post("/create")
async def create_token(
    request: Request,
    name: str = Form(...),
    permissions: str = Form("read"),
    expires_days: int = Form(0),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Generate raw token (shown once only)
    raw_token = f"nxt_{secrets.token_urlsafe(32)}"

    db = SessionLocal()
    try:
        token = ApiToken(
            name=name,
            token_hash=hash_token(raw_token),
            user_id=user["id"],
            permissions=permissions,
            expires_at=datetime.utcnow() + timedelta(days=expires_days) if expires_days > 0 else None,
        )
        db.add(token)
        db.commit()
        return JSONResponse(content={
            "success": True,
            "token": raw_token,
            "message": "Save this token — it won't be shown again!",
        })
    finally:
        db.close()


@router.post("/{token_id}/delete")
async def delete_token(request: Request, token_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        token = db.query(ApiToken).filter(
            ApiToken.id == token_id,
            ApiToken.user_id == user["id"]
        ).first()
        if token:
            db.delete(token)
            db.commit()
        return JSONResponse(content={"success": True})
    finally:
        db.close()


@router.post("/{token_id}/toggle")
async def toggle_token(request: Request, token_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        token = db.query(ApiToken).filter(
            ApiToken.id == token_id,
            ApiToken.user_id == user["id"]
        ).first()
        if token:
            token.enabled = not token.enabled
            db.commit()
        return JSONResponse(content={"success": True})
    finally:
        db.close()
