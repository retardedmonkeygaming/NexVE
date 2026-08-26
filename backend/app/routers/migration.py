"""
NexVE Migration Router
API endpoints for live migration of VMs and containers.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.migration_service import MigrationService
from ..auth import get_current_user

router = APIRouter()
migration_svc = MigrationService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/nodes")
async def list_nodes(request: Request):
    """List available nodes for migration."""
    user, redir = auth_check(request)
    if redir:
        return redir
    nodes = migration_svc.get_nodes()
    return JSONResponse({"nodes": nodes})


@router.post("/vm/{vm_id}/migrate")
async def migrate_vm(
    request: Request,
    vm_id: int,
    target_node: str = Form(...),
    live: bool = Form(True),
    force: bool = Form(False),
):
    """Migrate a VM to another node."""
    user, redir = auth_check(request)
    if redir:
        return redir

    from ..database import SessionLocal
    from ..models.vm import VM
    from ..services.vm_service import VMService

    vm_svc = VMService()
    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)

        result = migration_svc.migrate_vm(vm.name, target_node, live, force)
        return JSONResponse(result)
    finally:
        db.close()


@router.post("/container/{ct_id}/migrate")
async def migrate_container(
    request: Request,
    ct_id: int,
    target_node: str = Form(...),
):
    """Migrate a container to another node."""
    user, redir = auth_check(request)
    if redir:
        return redir

    result = migration_svc.migrate_container(ct_id, target_node)
    return JSONResponse(result)


@router.get("/status/{vm_name}")
async def migration_status(request: Request, vm_name: str):
    """Get migration status for a VM."""
    user, redir = auth_check(request)
    if redir:
        return redir
    status = migration_svc.get_migration_status(vm_name)
    return JSONResponse(status)


@router.post("/cancel/{vm_name}")
async def cancel_migration(request: Request, vm_name: str):
    """Cancel an in-progress migration."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = migration_svc.cancel_migration(vm_name)
    return JSONResponse(result)
