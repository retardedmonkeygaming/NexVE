"""Tags router: CRUD for color-coded labels on VMs/containers."""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.feature_models import VMTag, VMTagAssignment
from ..auth import get_current_user

router = APIRouter()


def auth_check(request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/")
async def list_tags(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        tags = db.query(VMTag).all()
        return JSONResponse({"tags": [
            {"id": t.id, "name": t.name, "color": t.color}
            for t in tags
        ]})
    finally:
        db.close()


@router.post("/create")
async def create_tag(request: Request, name: str = Form(...), color: str = Form("#f97316")):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        tag = VMTag(name=name, color=color)
        db.add(tag)
        db.commit()
        return JSONResponse({"success": True, "id": tag.id, "name": tag.name, "color": tag.color})
    finally:
        db.close()


@router.delete("/{tag_id}")
async def delete_tag(request: Request, tag_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        db.query(VMTagAssignment).filter(VMTagAssignment.tag_id == tag_id).delete()
        db.query(VMTag).filter(VMTag.id == tag_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/{tag_id}/assign")
async def assign_tag(request: Request, tag_id: int, target_type: str = Form(...), target_id: int = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        existing = db.query(VMTagAssignment).filter(
            VMTagAssignment.tag_id == tag_id,
            VMTagAssignment.target_type == target_type,
            VMTagAssignment.target_id == target_id,
        ).first()
        if not existing:
            assignment = VMTagAssignment(tag_id=tag_id, target_type=target_type, target_id=target_id)
            db.add(assignment)
            db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/{tag_id}/unassign")
async def unassign_tag(request: Request, tag_id: int, target_type: str = Form(...), target_id: int = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        db.query(VMTagAssignment).filter(
            VMTagAssignment.tag_id == tag_id,
            VMTagAssignment.target_type == target_type,
            VMTagAssignment.target_id == target_id,
        ).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.get("/for/{target_type}/{target_id}")
async def tags_for_target(request: Request, target_type: str, target_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        assignments = db.query(VMTagAssignment).filter(
            VMTagAssignment.target_type == target_type,
            VMTagAssignment.target_id == target_id,
        ).all()
        tag_ids = [a.tag_id for a in assignments]
        tags = db.query(VMTag).filter(VMTag.id.in_(tag_ids)).all() if tag_ids else []
        return JSONResponse({"tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags]})
    finally:
        db.close()
