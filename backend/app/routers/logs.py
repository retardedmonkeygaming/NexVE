from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.log_service import LogService
from ..auth import get_current_user

router = APIRouter()
log_service = LogService()


@router.get("/tasks")
async def list_tasks(request: Request, limit: int = 50):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content={"tasks": log_service.get_tasks(limit)})


@router.get("/audit")
async def list_audit_log(request: Request, limit: int = 100):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content={"logs": log_service.get_audit_log(limit)})


@router.get("/notifications")
async def list_notifications(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content={"notifications": log_service.get_notifications()})


@router.get("/notifications/unread-count")
async def unread_count(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse(content={"count": 0})
    notifs = log_service.get_notifications(unread_only=True)
    return JSONResponse(content={"count": len(notifs)})


@router.post("/notifications/{notif_id}/read")
async def mark_read(request: Request, notif_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    log_service.mark_read(notif_id)
    return JSONResponse(content={"success": True})


@router.post("/notifications/read-all")
async def mark_all_read(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    log_service.mark_all_read()
    return JSONResponse(content={"success": True})


@router.get("/syslog")
async def get_syslog(request: Request, lines: int = 200):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    import subprocess
    r = subprocess.run(
        f"journalctl --no-pager -n {lines} --output=short-iso",
        shell=True, capture_output=True, text=True, timeout=10
    )
    return JSONResponse(content={"log": r.stdout if r.success else "Failed to read syslog"})
