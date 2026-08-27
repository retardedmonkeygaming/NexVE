"""DHCP/DNS API Router"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.dhcp_dns_service import DHCPDNSService
from ..auth import get_current_user

router = APIRouter()
dhcp_svc = DHCPDNSService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/status")
async def dhcp_dns_status(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.get_status())


@router.get("/dhcp/ranges")
async def dhcp_ranges(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.list_dhcp_ranges())


@router.post("/dhcp/ranges/add")
async def add_dhcp_range(
    request: Request,
    start: str = Form(...),
    end: str = Form(...),
    netmask: str = Form("255.255.255.0"),
    lease_time: str = Form("24h"),
    interface: str = Form(""),
):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.add_dhcp_range(start, end, netmask, lease_time, interface))


@router.delete("/dhcp/ranges/remove")
async def remove_dhcp_range(
    request: Request,
    start: str = Form(...),
    end: str = Form(...),
):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.remove_dhcp_range(start, end))


@router.get("/dhcp/leases")
async def dhcp_leases(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.list_leases())


@router.post("/dhcp/static")
async def add_static_host(
    request: Request,
    mac: str = Form(...),
    ip: str = Form(...),
    name: str = Form(""),
):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.add_static_host(mac, ip, name))


@router.get("/dns/records")
async def dns_records(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.list_dns_records())


@router.post("/dns/records/add")
async def add_dns_record(
    request: Request,
    domain: str = Form(...),
    ip: str = Form(...),
):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.add_dns_record(domain, ip))


@router.delete("/dns/records/{domain}")
async def remove_dns_record(request: Request, domain: str):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.remove_dns_record(domain))


@router.post("/dns/upstream")
async def add_upstream_dns(
    request: Request,
    server: str = Form(...),
):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.add_upstream_dns(server))


@router.post("/restart")
async def restart_dnsmasq(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse(dhcp_svc.restart())


@router.get("/config")
async def get_config(request: Request):
    user, redir = auth_check(request)
    if redir: return redir
    return JSONResponse({"config": dhcp_svc.get_config_content()})
