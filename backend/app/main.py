from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import psutil
import os
import asyncio

from .routers import nodes, vms, containers, storage, network, users, setup, backups, console, monitor, activity, settings
from .auth import get_current_user
from .database import SessionLocal, engine
from .models.vm import VM, Container
from .models.user import User, Session
from .models.storage import Storage
from .models.activity import ActivityLog
from .middleware import SetupMiddleware
from .services.monitor_service import monitor_svc

# Create all tables
from .database import Base
Base.metadata.create_all(bind=engine)

app = FastAPI(title="NexVE", version="1.0.0")

# Middleware
app.add_middleware(SetupMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static + Templates
app.mount("/static", StaticFiles(directory="../frontend"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ── API Routers ──
app.include_router(nodes.router, prefix="/api/nodes", tags=["Nodes"])
app.include_router(vms.router, prefix="/api/vms", tags=["VMs"])
app.include_router(containers.router, prefix="/api/containers", tags=["Containers"])
app.include_router(storage.router, prefix="/api/storage", tags=["Storage"])
app.include_router(network.router, prefix="/api/network", tags=["Network"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(setup.router, prefix="/api/setup", tags=["Setup"])
app.include_router(backups.router, prefix="/api/backups", tags=["Backups"])
app.include_router(console.router, prefix="/api/console", tags=["Console"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["Monitor"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])


# ── Background monitor collector ──
@app.on_event("startup")
async def start_background_tasks():
    async def collect_loop():
        while True:
            monitor_svc.collect()
            await asyncio.sleep(10)
    asyncio.create_task(collect_loop())


# ── Page Routes ──
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"user": user})


@app.get("/vms", response_class=HTMLResponse)
async def vms_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="vms.html", context={"user": user})


@app.get("/containers", response_class=HTMLResponse)
async def containers_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="containers.html", context={"user": user})


@app.get("/storage", response_class=HTMLResponse)
async def storage_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="storage.html", context={"user": user})


@app.get("/network", response_class=HTMLResponse)
async def network_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="network.html", context={"user": user})


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="monitor.html", context={"user": user})


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="users.html", context={"user": user})


@app.get("/activity", response_class=HTMLResponse)
async def activity_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="activity.html", context={"user": user})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="settings.html", context={"user": user})


@app.get("/console/vm/{vm_id}", response_class=HTMLResponse)
async def vm_console_page(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request=request, name="console.html", context={"user": user, "vm_id": vm_id})


@app.get("/api/system")
async def system_info():
    return {
        "hostname": os.uname().nodename,
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_count": psutil.cpu_count(),
        "memory": psutil.virtual_memory()._asdict(),
        "disk": psutil.disk_usage("/")._asdict(),
    }
