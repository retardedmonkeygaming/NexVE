"""
NexVE SDN Router
API endpoints for Software-Defined Networking management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.sdn_service import SDNService
from ..auth import get_current_user, api_auth

router = APIRouter()
sdn_svc = SDNService()



@router.get("/status")
async def sdn_status(request: Request):
    """Get SDN status."""
    user, error = api_auth(request)
    if error: return error
    status = sdn_svc.get_sdn_status()
    return JSONResponse(status)


@router.get("/zones")
async def list_zones(request: Request):
    """List SDN zones."""
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    result = sdn_svc.create_zone(name, zone_type, bridge, mtu)
    return JSONResponse(result)


@router.delete("/zones/{name}")
async def delete_zone(name: str, request: Request):
    """Delete an SDN zone."""
    user, error = api_auth(request)
    if error: return error
    result = sdn_svc.delete_zone(name)
    return JSONResponse(result)


@router.get("/vnets")
async def list_vnets(request: Request):
    """List virtual networks."""
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    result = sdn_svc.create_vnet(name, zone_name, vlan_id, cidr, gateway)
    return JSONResponse(result)


@router.delete("/vnets/{name}")
async def delete_vnet(name: str, request: Request):
    """Delete a virtual network."""
    user, error = api_auth(request)
    if error: return error
    result = sdn_svc.delete_vnet(name)
    return JSONResponse(result)


@router.post("/apply")
async def apply_sdn(request: Request):
    """Apply SDN configuration."""
    user, error = api_auth(request)
    if error: return error
    result = sdn_svc.apply_sdn()
    return JSONResponse(result)


# ── Open vSwitch endpoints ──

@router.get("/ovs/status")
async def ovs_status(request: Request):
    """Get Open vSwitch status."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(sdn_svc.ovs_status())


@router.get("/ovs/bridges")
async def ovs_bridges(request: Request):
    """List OVS bridges."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"bridges": sdn_svc.ovs_list_bridges()})


@router.post("/ovs/bridge")
async def ovs_create_bridge(request: Request, name: str = Form(...)):
    """Create an OVS bridge."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(sdn_svc.ovs_create_bridge(name))


@router.delete("/ovs/bridge/{name}")
async def ovs_delete_bridge(name: str, request: Request):
    """Delete an OVS bridge."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(sdn_svc.ovs_delete_bridge(name))


@router.post("/ovs/port")
async def ovs_add_port(request: Request, bridge: str = Form(...), port: str = Form(...),
                       tag: int = Form(0), trunk: str = Form("")):
    """Add a port to an OVS bridge."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(sdn_svc.ovs_add_port(bridge, port, tag, trunk))


@router.delete("/ovs/port/{bridge}/{port}")
async def ovs_del_port(bridge: str, port: str, request: Request):
    """Remove a port from an OVS bridge."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(sdn_svc.ovs_del_port(bridge, port))


@router.get("/ovs/flows/{bridge}")
async def ovs_flows(bridge: str, request: Request):
    """List OpenFlow rules on a bridge."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"flows": sdn_svc.ovs_list_flows(bridge)})


@router.post("/ovs/flow")
async def ovs_add_flow(request: Request, bridge: str = Form(...), flow: str = Form(...)):
    """Add an OpenFlow rule."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(sdn_svc.ovs_add_flow(bridge, flow))


@router.get("/ovs/show")
async def ovs_show(request: Request):
    """Show full OVS configuration."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(sdn_svc.ovs_show())
