from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
import psutil
import platform
import subprocess
import os
import time

router = APIRouter()


def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception:
        return ""


@router.get("/")
async def list_nodes():
    boot = psutil.boot_time()
    uptime_sec = int(time.time() - boot)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    try:
        hostname = run_cmd("hostnamectl hostname 2>/dev/null || hostname")
    except Exception:
        hostname = platform.node()
    try:
        os_info = run_cmd("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2")
    except Exception:
        os_info = f"{platform.system()} {platform.release()}"

    return {
        "nodes": [{
            "name": hostname.strip() or platform.node(),
            "status": "online",
            "cpu": psutil.cpu_percent(interval=0.1),
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total": mem.total,
                "used": mem.used,
                "available": mem.available,
                "percent": mem.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            },
            "uptime": uptime_sec,
            "boot_time": boot,
            "os": os_info,
            "kernel": platform.release(),
            "arch": platform.machine(),
        }]
    }


@router.get("/{node_name}")
async def get_node(node_name: str):
    boot = psutil.boot_time()
    uptime_sec = int(time.time() - boot)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "name": node_name,
        "status": "online",
        "cpu": {
            "percent": psutil.cpu_percent(),
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        },
        "memory": mem._asdict(),
        "disk": disk._asdict(),
        "uptime": uptime_sec,
        "boot_time": boot,
        "platform": platform.platform(),
        "kernel": platform.release(),
        "os": run_cmd("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2") or platform.platform(),
    }


@router.post("/{node_name}/reboot")
async def reboot_node(node_name: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    from ..auth import get_current_user
    user = get_current_user(request)
    if not user or user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)
    import subprocess
    log_task(user.id, user.username, "node.reboot", "node", node_name, "completed")
    try:
        subprocess.Popen(["shutdown", "-r", "+0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
    return JSONResponse({"success": True, "message": "Reboot scheduled"})


@router.post("/{node_name}/shutdown")
async def shutdown_node(node_name: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    from ..auth import get_current_user
    user = get_current_user(request)
    if not user or user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)
    import subprocess
    log_task(user.id, user.username, "node.shutdown", "node", node_name, "completed")
    try:
        subprocess.Popen(["shutdown", "-h", "+0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
    return JSONResponse({"success": True, "message": "Shutdown scheduled"})
