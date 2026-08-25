from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.backup_service import BackupService
from ..auth import get_current_user

router = APIRouter()
svc = BackupService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


# ── VM Snapshots ──

@router.get("/vm/{vm_id}/snapshots")
async def vm_snapshots(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({"snapshots": svc.vm_snapshots(vm_id)})


@router.post("/vm/{vm_id}/snapshots")
async def vm_snapshot_create(request: Request, vm_id: int, name: str = Form(...), description: str = Form("")):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.vm_snapshot_create(vm_id, name, description))


@router.delete("/vm/{vm_id}/snapshots/{name}")
async def vm_snapshot_delete(request: Request, vm_id: int, name: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.vm_snapshot_delete(vm_id, name))


@router.post("/vm/{vm_id}/snapshots/{name}/restore")
async def vm_snapshot_restore(request: Request, vm_id: int, name: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.vm_snapshot_restore(vm_id, name))


# ── Container Snapshots ──

@router.get("/container/{ct_id}/snapshots")
async def container_snapshots(request: Request, ct_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({"snapshots": svc.container_snapshots(ct_id)})


@router.post("/container/{ct_id}/snapshots")
async def container_snapshot_create(request: Request, ct_id: int, name: str = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.container_snapshot_create(ct_id, name))


# ── Full Backups ──

@router.post("/vm/{vm_id}/backup")
async def backup_vm(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.backup_vm(vm_id))


@router.post("/container/{ct_id}/backup")
async def backup_container(request: Request, ct_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.backup_container(ct_id))


@router.get("/list")
async def list_backups(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({"backups": svc.list_backups()})


@router.delete("/{filename}")
async def delete_backup(request: Request, filename: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.delete_backup(filename))
