from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..database import SessionLocal
from ..models.user import User
from ..auth import get_current_user, api_auth

router = APIRouter()



@router.get("/")
async def list_users(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return JSONResponse({"users": [u.to_dict() for u in users]})
    finally:
        db.close()


@router.post("/create")
@router.post("/")
async def create_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), role: str = Form("user")):
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
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


# ── Groups ──

from ..models.user import Group, Role


@router.get("/groups")
async def list_groups(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        groups = db.query(Group).all()
        return JSONResponse({"groups": [{"id": g.id, "name": g.name, "description": g.description or ""} for g in groups]})
    finally:
        db.close()


@router.post("/groups/create")
async def create_group(request: Request, name: str = Form(...), description: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        existing = db.query(Group).filter(Group.name == name).first()
        if existing:
            return JSONResponse({"error": "Group already exists"}, status_code=400)
        group = Group(name=name, description=description)
        db.add(group)
        db.commit()
        return JSONResponse({"success": True, "id": group.id})
    finally:
        db.close()


@router.delete("/groups/{group_id}")
async def delete_group(request: Request, group_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        db.query(Group).filter(Group.id == group_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


# ── Roles ──

@router.get("/roles")
async def list_roles(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        roles = db.query(Role).all()
        if not roles:
            # Seed default roles
            defaults = [
                ("admin", "Full system access", "[\"*\"]"),
                ("auditor", "Read-only access", "[\"view\"]"),
                ("user", "Basic user access", "[\"vm.manage\", \"ct.manage\"]"),
            ]
            for name, desc, perms in defaults:
                if not db.query(Role).filter(Role.name == name).first():
                    db.add(Role(name=name, description=desc, permissions=perms))
            db.commit()
            roles = db.query(Role).all()
        return JSONResponse({"roles": [{"id": r.id, "name": r.name, "description": r.description or "", "permissions": r.permissions or "[]"} for r in roles]})
    finally:
        db.close()
