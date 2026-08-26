"""
NexVE SDN Router
API endpoints for Software-Defined Networking management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.sdn_service import SDNService
from ..auth import get_current_user

router = APIRouter()
sdn_svc = SDNService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/status")
async def sdn_status(request: Request):
    """Get SDN status."""
    user, redir = auth_check(request)
    if redir:
        return redir
    status = sdn_svc.get_sdn_status()
    return JSONResponse(status)


@router.get("/zones")
async def list_zones(request: Request):
    """List SDN zones."""
    user, redir = auth_check(request)
    if redir:
        return redir
    zones = sdn_svc.list_zones()
    return JSONResponse({"zones": zones})


@router.post("/zones")
async def create_zone(
    request: Request,
    name: str = Form(...),
    zone_type: str = Form("simple"),
    bridge: str = Form(""),
    mtu: int = Form(1500),
):
    """Create an SDN zone."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = sdn_svc.create_zone(name, zone_type, bridge, mtu)
    return JSONResponse(result)


@router.delete("/zones/{name}")
async def delete_zone(name: str, request: Request):
    """Delete an SDN zone."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = sdn_svc.delete_zone(name)
    return JSONResponse(result)


@router.get("/vnets")
async def list_vnets(request: Request):
    """List virtual networks."""
    user, redir = auth_check(request)
    if redir:
        return redir
    vnets = sdn_svc.list_vnets()
    return JSONResponse({"vnets": vnets})


@router.post("/vnets")
async def create_vnet(
    request: Request,
    name: str = Form(...),
    zone_name: str = Form(""),
    vlan_id: int = Form(0),
    cidr: str = Form(""),
    gateway: str = Form(""),
):
    """Create a virtual network."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = sdn_svc.create_vnet(name, zone_name, vlan_id, cidr, gateway)
    return JSONResponse(result)


@router.delete("/vnets/{name}")
async def delete_vnet(name: str, request: Request):
    """Delete a virtual network."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = sdn_svc.delete_vnet(name)
    return JSONResponse(result)


@router.post("/apply")
async def apply_sdn(request: Request):
    """Apply SDN configuration."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = sdn_svc.apply_sdn()
    return JSONResponse(result)
