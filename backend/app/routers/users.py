from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..database import SessionLocal
from ..models.user import User, Group, Role, ACL, PAMConfig
from ..auth import get_current_user, api_auth
import json
import subprocess

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


# ── Custom Roles CRUD ──

@router.post("/roles/create")
async def create_role(request: Request, name: str = Form(...), description: str = Form(""), permissions: str = Form("[]")):
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    db = SessionLocal()
    try:
        if db.query(Role).filter(Role.name == name).first():
            return JSONResponse({"success": False, "error": f"Role '{name}' already exists"})
        db.add(Role(name=name, description=description, permissions=permissions, builtin=False))
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/roles/{role_id}/update")
async def update_role(request: Request, role_id: int):
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    form = await request.form()
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return JSONResponse({"success": False, "error": "Role not found"})
        if role.builtin:
            return JSONResponse({"success": False, "error": "Cannot modify built-in roles"})
        if "description" in form:
            role.description = form["description"]
        if "permissions" in form:
            role.permissions = form["permissions"]
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.delete("/roles/{role_id}")
async def delete_role(request: Request, role_id: int):
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return JSONResponse({"success": False, "error": "Role not found"})
        if role.builtin:
            return JSONResponse({"success": False, "error": "Cannot delete built-in roles"})
        db.delete(role)
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


# ── Path-based ACL ──

@router.get("/acl")
async def list_acl(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        acls = db.query(ACL).all()
        return JSONResponse({"acls": [a.to_dict() for a in acls]})
    finally:
        db.close()


@router.post("/acl/create")
async def create_acl(request: Request, path: str = Form(...), subject_type: str = Form("user"),
                    subject_id: int = Form(...), role_id: int = Form(...)):
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    db = SessionLocal()
    try:
        db.add(ACL(path=path, subject_type=subject_type, subject_id=subject_id, role_id=role_id))
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.delete("/acl/{acl_id}")
async def delete_acl(request: Request, acl_id: int):
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    db = SessionLocal()
    try:
        db.query(ACL).filter(ACL.id == acl_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/acl/{acl_id}/toggle")
async def toggle_acl(request: Request, acl_id: int):
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    db = SessionLocal()
    try:
        acl = db.query(ACL).filter(ACL.id == acl_id).first()
        if acl:
            acl.enabled = not acl.enabled
            db.commit()
        return JSONResponse({"success": True, "enabled": acl.enabled if acl else False})
    finally:
        db.close()


# ── PAM Integration ──

@router.get("/pam/status")
async def pam_status(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        config = db.query(PAMConfig).first()
        if not config:
            config = PAMConfig(enabled=False, map_to_role="user")
            db.add(config)
            db.commit()
            db.refresh(config)
        return JSONResponse({
            "enabled": config.enabled,
            "map_to_role": config.map_to_role,
            "allowed_groups": json.loads(config.allowed_groups) if config.allowed_groups else [],
            "deny_groups": json.loads(config.deny_groups) if config.deny_groups else [],
        })
    finally:
        db.close()


@router.post("/pam/configure")
async def configure_pam(request: Request, enabled: str = Form("false"),
                        map_to_role: str = Form("user"),
                        allowed_groups: str = Form(""),
                        deny_groups: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    db = SessionLocal()
    try:
        config = db.query(PAMConfig).first()
        if not config:
            config = PAMConfig()
            db.add(config)
        config.enabled = enabled.lower() in ("true", "on", "1")
        config.map_to_role = map_to_role
        if allowed_groups:
            config.allowed_groups = json.dumps([g.strip() for g in allowed_groups.split(",") if g.strip()])
        if deny_groups:
            config.deny_groups = json.dumps([g.strip() for g in deny_groups.split(",") if g.strip()])
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/pam/authenticate")
async def pam_authenticate(request: Request, username: str = Form(...), password: str = Form(...)):
    """Authenticate a user against PAM."""
    # Check PAM is enabled
    db = SessionLocal()
    try:
        config = db.query(PAMConfig).first()
        if not config or not config.enabled:
            return JSONResponse({"success": False, "error": "PAM authentication not enabled"})
    finally:
        db.close()

    # Try PAM authentication via pam_authenticate
    try:
        result = subprocess.run(
            ["python3", "-c", f"\nimport pam\np = pam.pam()\nresult = p.authenticate('{username}', '{password}')\nprint('SUCCESS' if result else 'FAILED')\n"],
            capture_output=True, text=True, timeout=10
        )
        if "SUCCESS" in result.stdout:
            # Check if user exists in NexVE, create if needed
            db = SessionLocal()
            try:
                nexve_user = db.query(User).filter(User.username == username).first()
                if not nexve_user:
                    from ..security import hash_password
                    nexve_user = User(
                        username=username,
                        email=f"{username}@pam.local",
                        password_hash=hash_password("pam-managed"),
                        role=config.map_to_role or "user",
                    )
                    db.add(nexve_user)
                    db.commit()
                return JSONResponse({"success": True, "user": nexve_user.to_dict()})
            finally:
                db.close()
        else:
            return JSONResponse({"success": False, "error": "PAM authentication failed"})
    except FileNotFoundError:
        return JSONResponse({"success": False, "error": "PAM module not available. Install: pip install python-pam"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
