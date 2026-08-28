from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime
import os
import psutil

from .database import engine, Base, SessionLocal
from .auth import get_current_user, create_session, verify_totp
from .models.user import User, Session, AuditLog, Notification, Task
from .models.vm import VM, Container, BackupSchedule, ApiToken
from .models.firewall import FirewallRule, FirewallGroup
from .models.storage import Storage
from .models.template import ISOImage
from .models.activity import ActivityLog
from .models.feature_models import (
    VMTag, VMTagAssignment, ResourcePool, ResourcePoolMember,
    LDAPConfig, ClientCertConfig, NetworkSecurityGroup, SecurityGroupRule,
    SecurityGroupAssignment, NetworkFirewallAlias, FirewallAliasEntry,
    NetworkRateLimit, WebAuthnCredential, DatacenterFirewallRule,
    DatacenterSettings, MetricServer, RegisteredTag, LDAPDomainMapping,
    APITokenACL,
)
from .models.enhanced_models import (
    MigrationJob, HAGroup, HAGuest, ClusterNode, ClusterConfig,
    SDNZone, SDNVnet, CephConfig, SSLCertificate, ACMEAccount,
    BackupRecord, BackupRemote, NotificationTarget, NotificationRule,
    SystemSetting, SettingsHistory, UserSSHKey, UserQuota, UserSession,
    StorageTier, FirewallStats, VMFirewallRule, FirewallMacro,
)
from .security import generate_csrf_token

# Import all routers
from .routers import (
    nodes, vms, containers, storage, network, users, setup,
    shell, settings, login, two_factor, console, backups,
    monitor, firewall, logs, activity, api_tokens, templates_route,
    tags, resource_pools, ldap,
)
from .routers import (
    migration, ha, cluster, cluster_mgmt, sdn, ceph, acme, notifications,
    wireguard, dhcp_dns, oidc, datacenter,
)

# Create all tables
Base.metadata.create_all(bind=engine)

# Auto-migrate: add new columns to existing tables
try:
    from .database import migrate_database
    migrate_database()
except Exception:
    pass

app = FastAPI(title="NexVE", version="3.0.0")

# Mount static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "../../static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "./templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# ─── Include routers ───
# Login (no prefix — defines /login routes)
app.include_router(login.router, tags=["Login"])
# Setup
app.include_router(setup.router, prefix="/setup", tags=["Setup"])
# 2FA settings (no prefix — defines /settings/2fa routes)
app.include_router(two_factor.router, tags=["2FA"])

# API routers
app.include_router(nodes.router, prefix="/api/nodes", tags=["Nodes"])
app.include_router(vms.router, prefix="/api/vms", tags=["VMs"])
app.include_router(containers.router, prefix="/api/containers", tags=["Containers"])
app.include_router(storage.router, prefix="/api/storage", tags=["Storage"])
app.include_router(network.router, prefix="/api/network", tags=["Network"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(console.router, prefix="/api/console", tags=["Console"])
app.include_router(backups.router, prefix="/api/backups", tags=["Backups"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["Monitor"])
app.include_router(firewall.router, prefix="/api/firewall", tags=["Firewall"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity"])
app.include_router(api_tokens.router, prefix="/api/tokens", tags=["API Tokens"])
app.include_router(templates_route.router, prefix="/templates", tags=["Templates"])
app.include_router(shell.router, prefix="/api/shell", tags=["Shell"])
# New routers
app.include_router(tags.router, prefix="/api/tags", tags=["Tags"])
app.include_router(resource_pools.router, prefix="/api/resource-pools", tags=["Resource Pools"])
app.include_router(ldap.router, prefix="/api/ldap", tags=["LDAP"])
# New v3.0 routers
app.include_router(migration.router, prefix="/api/migration", tags=["Migration"])
app.include_router(ha.router, prefix="/api/ha", tags=["High Availability"])
app.include_router(cluster.router, prefix="/api/cluster", tags=["Cluster"])
app.include_router(cluster_mgmt.router, prefix="/api/cluster-mgmt", tags=["Cluster Management"])
app.include_router(sdn.router, prefix="/api/sdn", tags=["SDN"])
app.include_router(ceph.router, prefix="/api/ceph", tags=["Ceph"])
app.include_router(wireguard.router, prefix="/api/wireguard", tags=["WireGuard VPN"])
app.include_router(dhcp_dns.router, prefix="/api/dhcp-dns", tags=["DHCP/DNS"])
app.include_router(oidc.router, prefix="/auth/oidc", tags=["OIDC"])
app.include_router(acme.router, prefix="/api/acme", tags=["ACME"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(datacenter.router, prefix="/api/datacenter", tags=["Datacenter"])


# ─── Start background monitor collector ───
@app.on_event("startup")
async def startup_event():
    from .services.monitor_service import MonitorService
    monitor = MonitorService()
    monitor.start_collector()


# ─── Global exception handler — return JSON for API, HTML for pages ───
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    path = request.url.path
    if path.startswith("/api/") or request.headers.get("accept", "").startswith("application/json"):
        return JSONResponse(
            {"error": str(exc), "type": type(exc).__name__, "detail": tb[-500:] if len(tb) > 500 else tb},
            status_code=500,
        )
    return HTMLResponse(f"<h1>500 Internal Server Error</h1><pre>{tb}</pre>", status_code=500)


# ─── Middleware: Force setup if no admin exists ───
@app.middleware("http")
async def setup_middleware(request: Request, call_next):
    path = request.url.path
    # Allow static, login, and API endpoints through
    always_allowed = ["/login", "/login/2fa", "/static", "/favicon.ico"]
    if any(path.startswith(a) for a in always_allowed):
        return await call_next(request)
    # API endpoints: check auth (setup endpoints need special handling)
    if path.startswith("/api/"):
        return await call_next(request)

    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            # Only allow /setup when no users exist
            if path.startswith("/setup"):
                return await call_next(request)
            return RedirectResponse(url="/setup", status_code=303)
        else:
            # Block setup page when users already exist (prevent re-init attack)
            # But allow reset/factory-reset POST endpoints (they require admin auth)
            if path.startswith("/setup") and not (path.startswith("/setup/reset") or path.startswith("/setup/factory-reset")):
                return RedirectResponse(url="/login", status_code=303)
    finally:
        db.close()

    return await call_next(request)


# ─── Helper: Log task ───
from .task_utils import log_task


# ─── Pages ───

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))

    cpu = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user": user, "csrf_token": csrf, "page": "dashboard",
        "hostname": os.uname().nodename,
        "cpu": cpu, "memory": memory, "disk": disk,
    })


@app.get("/vms", response_class=HTMLResponse)
async def vms_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="vms.html", context={
        "user": user, "csrf_token": csrf, "page": "vms", "hostname": os.uname().nodename
    })


@app.get("/containers", response_class=HTMLResponse)
async def containers_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="containers.html", context={
        "user": user, "csrf_token": csrf, "page": "containers", "hostname": os.uname().nodename
    })


@app.get("/storage", response_class=HTMLResponse)
async def storage_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="storage.html", context={
        "user": user, "csrf_token": csrf, "page": "storage", "hostname": os.uname().nodename
    })


@app.get("/network", response_class=HTMLResponse)
async def network_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="network.html", context={
        "user": user, "csrf_token": csrf, "page": "network", "hostname": os.uname().nodename
    })


@app.get("/firewall", response_class=HTMLResponse)
async def firewall_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="firewall.html", context={
        "user": user, "csrf_token": csrf, "page": "firewall", "hostname": os.uname().nodename
    })


@app.get("/backups", response_class=HTMLResponse)
async def backups_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="backups.html", context={
        "user": user, "csrf_token": csrf, "page": "backups", "hostname": os.uname().nodename
    })


@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="monitor.html", context={
        "user": user, "csrf_token": csrf, "page": "monitoring", "hostname": os.uname().nodename
    })


@app.get("/cluster", response_class=HTMLResponse)
async def cluster_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="cluster.html", context={
        "user": user, "csrf_token": csrf, "page": "cluster", "hostname": os.uname().nodename
    })


@app.get("/ceph", response_class=HTMLResponse)
async def ceph_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="ceph.html", context={
        "user": user, "csrf_token": csrf, "page": "ceph", "hostname": os.uname().nodename
    })


@app.get("/wireguard", response_class=HTMLResponse)
async def wireguard_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="wireguard.html", context={
        "user": user, "csrf_token": csrf, "page": "wireguard", "hostname": os.uname().nodename
    })


@app.get("/console/{vm_id}", response_class=HTMLResponse)
async def console_page(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="console.html", context={
        "user": user, "csrf_token": csrf, "page": "console", "hostname": os.uname().nodename, "vm_id": vm_id
    })


@app.get("/shell", response_class=HTMLResponse)
async def shell_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="shell.html", context={
        "user": user, "page": "shell", "hostname": os.uname().nodename
    })


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="users.html", context={
        "user": user, "csrf_token": csrf, "page": "users", "hostname": os.uname().nodename
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "user": user, "csrf_token": csrf, "page": "settings", "hostname": os.uname().nodename
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="logs.html", context={
        "user": user, "csrf_token": csrf, "page": "logs", "hostname": os.uname().nodename
    })


# ─── 2FA Login ───

@app.get("/login/2fa", response_class=HTMLResponse)
async def login_2fa_page(request: Request):
    temp_token = request.cookies.get("nexve_temp_session")
    if not temp_token:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="login_2fa.html", context={
        "error": None
    })


@app.post("/login/2fa", response_class=HTMLResponse)
async def login_2fa_submit(
    request: Request,
    totp_code: str = Form(...),
):
    temp_token = request.cookies.get("nexve_temp_session")
    if not temp_token:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        session = db.query(Session).filter(Session.token == temp_token).first()
        if not session or session.expires_at < datetime.utcnow():
            return RedirectResponse(url="/login", status_code=302)

        user = db.query(User).filter(User.id == session.user_id).first()
        if not user:
            return RedirectResponse(url="/login", status_code=302)

        if not verify_totp(user.totp_secret, totp_code):
            return templates.TemplateResponse(request=request, name="login_2fa.html", context={
                "error": "Invalid 2FA code. Try again."
            })

        from .auth import destroy_session
        destroy_session(temp_token)

        token = create_session(user.id)
        log_task(user.id, user.username, "login (2FA)", "auth")
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("nexve_session", token, httponly=True, max_age=86400)
        response.delete_cookie("nexve_temp_session")
        return response
    finally:
        db.close()


# ─── Logout ───

@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("nexve_session")
    if token:
        from .auth import destroy_session
        destroy_session(token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("nexve_session")
    return response


# ─── API: Notifications ───

@app.get("/api/notifications")
async def api_notifications(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"notifications": [], "unread": 0})

    db = SessionLocal()
    try:
        notifs = db.query(Notification).order_by(Notification.created_at.desc()).limit(20).all()
        unread = db.query(Notification).filter(Notification.is_read == False).count()
        return JSONResponse({
            "notifications": [
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "level": n.level,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else "",
                }
                for n in notifs
            ],
            "unread": unread
        })
    finally:
        db.close()


@app.post("/api/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: int, request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = SessionLocal()
    try:
        n = db.query(Notification).filter(Notification.id == notif_id).first()
        if n:
            n.is_read = True
            db.commit()
        return JSONResponse({"ok": True})
    finally:
        db.close()


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    db = SessionLocal()
    try:
        db.query(Notification).filter(Notification.is_read == False).update({"is_read": True})
        db.commit()
        return JSONResponse({"ok": True})
    finally:
        db.close()


# ─── API: Task Log ───

@app.get("/api/tasks")
async def api_tasks(request: Request, limit: int = 50):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"tasks": []})

    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.started_at.desc()).limit(limit).all()
        return JSONResponse({
            "tasks": [
                {
                    "id": t.id,
                    "username": t.username,
                    "action": t.action,
                    "target_type": t.target_type,
                    "target_name": t.target_name,
                    "status": t.status,
                    "started_at": t.started_at.isoformat() if t.started_at else "",
                    "finished_at": t.finished_at.isoformat() if t.finished_at else "",
                }
                for t in tasks
            ]
        })
    finally:
        db.close()


# ─── API: Search ───

@app.get("/api/search")
async def api_search(request: Request, q: str = ""):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"results": []})

    if not q or len(q) < 2:
        return JSONResponse({"results": []})

    db = SessionLocal()
    try:
        results = []

        vms = db.query(VM).filter(VM.name.contains(q)).limit(10).all()
        for vm in vms:
            results.append({
                "type": "vm", "name": vm.name, "status": vm.status,
                "url": "/vms", "icon": "💻"
            })

        containers = db.query(Container).filter(Container.name.contains(q)).limit(10).all()
        for c in containers:
            results.append({
                "type": "container", "name": c.name, "status": c.status,
                "url": "/containers", "icon": "📦"
            })

        storages = db.query(Storage).filter(Storage.name.contains(q)).limit(10).all()
        for s in storages:
            results.append({
                "type": "storage", "name": s.name, "status": s.type,
                "url": "/storage", "icon": "💾"
            })

        return JSONResponse({"results": results})
    finally:
        db.close()


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = ""):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    return templates.TemplateResponse(request=request, name="search.html", context={
        "user": user, "csrf_token": csrf, "page": "search", "query": q, "hostname": os.uname().nodename
    })
