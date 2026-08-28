"""
NexVE ACME Router
API endpoints for SSL/T certificate management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.acme_service import ACMEService
from ..auth import get_current_user, api_auth

router = APIRouter()
acme_svc = ACMEService()



@router.get("/status")
async def acme_status(request: Request):
    """Get ACME status."""
    user, error = api_auth(request)
    if error: return error
    status = acme_svc.get_status()
    return JSONResponse(status)


@router.get("/certificates")
async def list_certificates(request: Request):
    """List managed certificates."""
    user, error = api_auth(request)
    if error: return error
    certs = acme_svc.list_certificates()
    return JSONResponse({"certificates": certs})


@router.post("/provision")
async def provision_certificate(
    request: Request,
    domain: str = Form(...),
    email: str = Form(""),
    challenge_type: str = Form("http"),
):
    """Provision a new certificate."""
    user, error = api_auth(request)
    if error: return error
    result = acme_svc.provision_certificate(domain, email, challenge_type)
    return JSONResponse(result)


@router.post("/upload")
async def upload_certificate(
    request: Request,
    domain: str = Form(...),
    cert_content: str = Form(...),
    key_content: str = Form(...),
):
    """Upload a custom certificate."""
    user, error = api_auth(request)
    if error: return error
    result = acme_svc.upload_certificate(domain, cert_content, key_content)
    return JSONResponse(result)


@router.post("/apply")
async def apply_certificate(
    request: Request,
    domain: str = Form(...),
):
    """Apply certificate to web server."""
    user, error = api_auth(request)
    if error: return error
    result = acme_svc.apply_certificate(domain)
    return JSONResponse(result)


@router.post("/renew")
async def renew_certificates(request: Request):
    """Renew all certificates."""
    user, error = api_auth(request)
    if error: return error
    result = acme_svc.renew_certificates()
    return JSONResponse(result)


@router.delete("/{domain}")
async def delete_certificate(domain: str, request: Request):
    """Delete a certificate."""
    user, error = api_auth(request)
    if error: return error
    result = acme_svc.delete_certificate(domain)
    return JSONResponse(result)
