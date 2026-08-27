"""OpenID Connect Authentication Router"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.oidc_service import OIDCService
from ..auth import get_current_user

router = APIRouter()
oidc_svc = OIDCService()


@router.get("/status")
async def oidc_status(request: Request):
    return JSONResponse({
        "configured": oidc_svc.is_configured(),
        "config": oidc_svc.get_config(),
    })


@router.post("/config")
async def save_oidc_config(
    request: Request,
    issuer: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    redirect_uri: str = Form(""),
    scope: str = Form("openid email profile"),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(oidc_svc.save_config(issuer, client_id, client_secret, redirect_uri, scope))


@router.get("/auth")
async def oidc_auth(request: Request):
    result = oidc_svc.generate_auth_url()
    if result.get("success"):
        return RedirectResponse(url=result["auth_url"], status_code=302)
    return JSONResponse(result, status_code=400)


@router.get("/callback")
async def oidc_callback(request: Request):
    code = request.query_params.get("code", "")
    state = request.query_params.get("state", "")
    
    if not oidc_svc.validate_state(state):
        return RedirectResponse(url="/login?error=invalid_state", status_code=302)
    
    # In production, exchange code for tokens and create/find user
    return RedirectResponse(url="/", status_code=302)


@router.post("/disable")
async def oidc_disable(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(oidc_svc.disable())
