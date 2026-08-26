"""LDAP configuration and management."""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.feature_models import LDAPConfig
from ..auth import get_current_user
from ..services.ldap_service import LDAPService

router = APIRouter()
ldap_svc = LDAPService()


def auth_check(request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/")
async def get_ldap_config(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        config = db.query(LDAPConfig).first()
        if not config:
            config = LDAPConfig()
            db.add(config)
            db.commit()
            db.refresh(config)
        return JSONResponse({
            "id": config.id,
            "enabled": config.enabled,
            "host": config.host,
            "port": config.port,
            "use_tls": config.use_tls,
            "bind_dn": config.bind_dn,
            "bind_password": "****" if config.bind_password else "",
            "base_dn": config.base_dn,
            "user_filter": config.user_filter,
            "group_filter": config.group_filter,
            "username_attr": config.username_attr,
            "email_attr": config.email_attr,
            "admin_group": config.admin_group,
            "auditor_group": config.auditor_group,
        })
    finally:
        db.close()


@router.post("/save")
async def save_ldap_config(
    request: Request,
    enabled: bool = Form(False),
    host: str = Form(""),
    port: int = Form(636),
    use_tls: bool = Form(True),
    bind_dn: str = Form(""),
    bind_password: str = Form(""),
    base_dn: str = Form(""),
    user_filter: str = Form("(objectClass=person)"),
    group_filter: str = Form("(objectClass=group)"),
    username_attr: str = Form("sAMAccountName"),
    email_attr: str = Form("mail"),
    admin_group: str = Form("Domain Admins"),
    auditor_group: str = Form("Domain Users"),
):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        config = db.query(LDAPConfig).first()
        if not config:
            config = LDAPConfig()
            db.add(config)

        config.enabled = enabled
        config.host = host
        config.port = port
        config.use_tls = use_tls
        config.bind_dn = bind_dn
        if bind_password != "****":
            config.bind_password = bind_password
        config.base_dn = base_dn
        config.user_filter = user_filter
        config.group_filter = group_filter
        config.username_attr = username_attr
        config.email_attr = email_attr
        config.admin_group = admin_group
        config.auditor_group = auditor_group
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/test")
async def test_ldap_connection(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = ldap_svc.test_connection()
    return JSONResponse(result)


@router.post("/search")
async def search_ldap_users(request: Request, query: str = Form("")):
    user, redir = auth_check(request)
    if redir:
        return redir
    users = ldap_svc.search_users(query)
    return JSONResponse({"users": users})
