"""Resource Pools: group VMs/containers with CPU/memory/disk quotas."""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.feature_models import ResourcePool, ResourcePoolMember
from ..auth import get_current_user

router = APIRouter()


def auth_check(request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/")
async def list_pools(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        pools = db.query(ResourcePool).all()
        result = []
        for p in pools:
            members = db.query(ResourcePoolMember).filter(ResourcePoolMember.pool_id == p.id).all()
            result.append({
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "cpu_quota": p.cpu_quota,
                "cpu_limit": p.cpu_limit,
                "memory_quota": p.memory_quota,
                "memory_limit": p.memory_limit,
                "disk_quota": p.disk_quota,
                "enabled": p.enabled,
                "members": [{"type": m.target_type, "id": m.target_id} for m in members],
            })
        return JSONResponse({"pools": result})
    finally:
        db.close()


@router.post("/create")
async def create_pool(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    cpu_quota: str = Form(""),
    cpu_limit: str = Form(""),
    memory_quota: str = Form(""),
    memory_limit: str = Form(""),
    disk_quota: str = Form(""),
):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        pool = ResourcePool(
            name=name,
            description=description,
            cpu_quota=float(cpu_quota) if cpu_quota else None,
            cpu_limit=float(cpu_limit) if cpu_limit else None,
            memory_quota=int(memory_quota) if memory_quota else None,
            memory_limit=int(memory_limit) if memory_limit else None,
            disk_quota=float(disk_quota) if disk_quota else None,
        )
        db.add(pool)
        db.commit()
        return JSONResponse({"success": True, "id": pool.id})
    finally:
        db.close()


@router.delete("/{pool_id}")
async def delete_pool(request: Request, pool_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        db.query(ResourcePoolMember).filter(ResourcePoolMember.pool_id == pool_id).delete()
        db.query(ResourcePool).filter(ResourcePool.id == pool_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/{pool_id}/add-member")
async def add_member(request: Request, pool_id: int, target_type: str = Form(...), target_id: int = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        existing = db.query(ResourcePoolMember).filter(
            ResourcePoolMember.pool_id == pool_id,
            ResourcePoolMember.target_type == target_type,
            ResourcePoolMember.target_id == target_id,
        ).first()
        if not existing:
            member = ResourcePoolMember(pool_id=pool_id, target_type=target_type, target_id=target_id)
            db.add(member)
            db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/{pool_id}/remove-member")
async def remove_member(request: Request, pool_id: int, target_type: str = Form(...), target_id: int = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        db.query(ResourcePoolMember).filter(
            ResourcePoolMember.pool_id == pool_id,
            ResourcePoolMember.target_type == target_type,
            ResourcePoolMember.target_id == target_id,
        ).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/{pool_id}/update")
async def update_pool(
    request: Request,
    pool_id: int,
    name: str = Form(""),
    description: str = Form(""),
    cpu_quota: str = Form(""),
    cpu_limit: str = Form(""),
    memory_quota: str = Form(""),
    memory_limit: str = Form(""),
    disk_quota: str = Form(""),
    enabled: bool = Form(True),
):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        pool = db.query(ResourcePool).filter(ResourcePool.id == pool_id).first()
        if not pool:
            return JSONResponse({"error": "Not found"}, status_code=404)
        if name:
            pool.name = name
        pool.description = description
        pool.cpu_quota = float(cpu_quota) if cpu_quota else None
        pool.cpu_limit = float(cpu_limit) if cpu_limit else None
        pool.memory_quota = int(memory_quota) if memory_quota else None
        pool.memory_limit = int(memory_limit) if memory_limit else None
        pool.disk_quota = float(disk_quota) if disk_quota else None
        pool.enabled = enabled
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()
