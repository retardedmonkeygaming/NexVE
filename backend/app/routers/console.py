from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.console_service import console_svc
from ..auth import get_current_user
import asyncio
try:
    import websockets
except ImportError:
    websockets = None
import subprocess

router = APIRouter()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/vm/{vm_id}")
async def vm_console(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = console_svc.console_for_vm(vm_id)
    return JSONResponse(result)


@router.get("/vm/{vm_id}/stop")
async def stop_vm_console(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = console_svc.stop_novnc(vm_id)
    return JSONResponse(result)


@router.get("/container/{ct_id}")
async def container_console(request: Request, ct_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = console_svc.console_for_container(ct_id)
    return JSONResponse(result)
