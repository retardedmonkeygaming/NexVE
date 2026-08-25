from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.network_service import NetworkService
from ..auth import get_current_user
import json

router = APIRouter()
svc = NetworkService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/overview")
async def network_overview(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.get_network_overview())


@router.get("/interfaces")
async def list_interfaces(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({"interfaces": svc.list_interfaces()})


# ── Bridges ──

@router.get("/bridges")
async def list_bridges(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({"bridges": svc.list_bridges()})


@router.post("/bridges")
async def create_bridge(request: Request, name: str = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = svc.create_bridge(name)
    return JSONResponse(result)


@router.delete("/bridges/{name}")
async def delete_bridge(request: Request, name: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = svc.delete_bridge(name)
    return JSONResponse(result)


@router.post("/bridges/{bridge}/ports")
async def add_port(request: Request, bridge: str, iface: str = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = svc.add_port(bridge, iface)
    return JSONResponse(result)


@router.delete("/bridges/{bridge}/ports/{iface}")
async def remove_port(request: Request, bridge: str, iface: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = svc.remove_port(iface)
    return JSONResponse(result)


# ── VLANs ──

@router.get("/vlans")
async def list_vlans(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({"vlans": svc.list_vlans()})


@router.post("/vlans")
async def create_vlan(request: Request, parent: str = Form(...), vlan_id: int = Form(...), name: str = Form("")):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = svc.create_vlan(parent, vlan_id, name)
    return JSONResponse(result)


@router.delete("/vlans/{name}")
async def delete_vlan(request: Request, name: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = svc.delete_vlan(name)
    return JSONResponse(result)


# ── Bonds ──

@router.get("/bonds")
async def list_bonds(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({"bonds": svc.list_bonds()})


@router.post("/bonds")
async def create_bond(request: Request, name: str = Form(...), mode: str = Form("balance-rr"), slaves: str = Form("")):
    user, redir = auth_check(request)
    if redir:
        return redir
    slave_list = [s.strip() for s in slaves.split(",") if s.strip()]
    result = svc.create_bond(name, mode, slave_list)
    return JSONResponse(result)


@router.delete("/bonds/{name}")
async def delete_bond(request: Request, name: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = svc.delete_bond(name)
    return JSONResponse(result)


# ── Firewall ──

@router.get("/firewall")
async def firewall_rules(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.firewall_rules())


@router.post("/firewall/enable")
async def firewall_enable(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.firewall_enable())


@router.post("/firewall/disable")
async def firewall_disable(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.firewall_disable())


@router.post("/firewall/rules")
async def add_firewall_rule(request: Request, rule: str = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(svc.firewall_add_rule(rule))
