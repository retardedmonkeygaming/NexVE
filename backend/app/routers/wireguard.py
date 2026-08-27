"""WireGuard VPN API Router"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.wireguard_service import WireGuardService
from ..auth import get_current_user

router = APIRouter()
wg_svc = WireGuardService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/status")
async def wg_status(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse({
        "available": wg_svc.is_available(),
        "interfaces": wg_svc.list_interfaces(),
        "traffic": wg_svc.get_traffic_stats(),
    })


@router.post("/interfaces/create")
async def wg_create_interface(
    request: Request,
    name: str = Form("wg0"),
    listen_port: int = Form(51820),
    address: str = Form(""),
):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(wg_svc.create_interface(name, listen_port, address))


@router.delete("/interfaces/{name}")
async def wg_delete_interface(request: Request, name: str):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(wg_svc.delete_interface(name))


@router.get("/interfaces/{name}/config")
async def wg_get_config(request: Request, name: str):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse({"config": wg_svc.get_config(name)})


@router.post("/peers/add")
async def wg_add_peer(
    request: Request,
    interface: str = Form(...),
    public_key: str = Form(...),
    endpoint: str = Form(""),
    allowed_ips: str = Form("0.0.0.0/0"),
    keepalive: int = Form(0),
):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(wg_svc.add_peer(interface, public_key, endpoint, allowed_ips, keepalive))


@router.delete("/peers/{interface}/{public_key}")
async def wg_remove_peer(request: Request, interface: str, public_key: str):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(wg_svc.remove_peer(interface, public_key))


@router.post("/generate-key")
async def wg_generate_key(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(wg_svc.generate_key())
