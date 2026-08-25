from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import psutil
import os

from .routers import nodes, vms, storage, network, users

app = FastAPI(title="NexVE", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="../frontend"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(nodes.router, prefix="/api/nodes", tags=["Nodes"])
app.include_router(vms.router, prefix="/api/vms", tags=["VMs"])
app.include_router(storage.router, prefix="/api/storage", tags=["Storage"])
app.include_router(network.router, prefix="/api/network", tags=["Network"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])

@app.get("/", response_class=HTMLResponse)
async def dashboard(request):
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "hostname": os.uname().nodename
    })

@app.get("/api/system")
async def system_info():
    return {
        "hostname": os.uname().nodename,
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_count": psutil.cpu_count(),
        "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        "memory": psutil.virtual_memory()._asdict(),
        "disk": psutil.disk_usage('/')._asdict(),
        "boot_time": psutil.boot_time(),
    }
