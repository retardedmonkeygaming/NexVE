from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..database import SessionLocal
from ..models.user import User
from ..auth import get_current_user

router = APIRouter()


def require_admin(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        if not db_user or db_user.role != "admin":
            return None, JSONResponse({"error": "Admin required"}, status_code=403)
    finally:
        db.close()
    return user, None


@router.get("/")
async def list_users(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return JSONResponse({"users": [u.to_dict() for u in users]})
    finally:
        db.close()


@router.post("/")
async def create_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), role: str = Form("user")):
    user, redir = require_admin(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing:
            return JSONResponse({"error": "Username or email already exists"}, status_code=400)
        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        db.add(new_user)
        db.commit()
        return JSONResponse({"success": True, "user": new_user.to_dict()})
    finally:
        db.close()


@router.put("/{user_id}")
async def update_user(request: Request, user_id: int, role: str = Form(...), is_active: bool = Form(True)):
    user, redir = require_admin(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if not target:
            return JSONResponse({"error": "User not found"}, status_code=404)
        target.role = role
        target.is_active = is_active
        db.commit()
        return JSONResponse({"success": True, "user": target.to_dict()})
    finally:
        db.close()


@router.delete("/{user_id}")
async def delete_user(request: Request, user_id: int):
    user, redir = require_admin(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if not target:
            return JSONResponse({"error": "User not found"}, status_code=404)
        db.delete(target)
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/{user_id}/reset-password")
async def reset_password(request: Request, user_id: int, password: str = Form(...)):
    user, redir = require_admin(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == user_id).first()
        if not target:
            return JSONResponse({"error": "User not found"}, status_code=404)
        target.set_password(password)
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()
