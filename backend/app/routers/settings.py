from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from ..auth import get_current_user
import subprocess
import os
import platform

router = APIRouter()


def auth_check(request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


def run_cmd(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}


@router.get("/system")
async def system_info(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse({
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "kernel": platform.version(),
        "arch": platform.machine(),
        "python": platform.python_version(),
    })


@router.post("/hostname")
async def set_hostname(request: Request, hostname: str = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = run_cmd(f"hostnamectl set-hostname {hostname}")
    return JSONResponse(result)


@router.get("/updates")
async def check_updates(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    run_cmd("apt update -qq")
    result = run_cmd("apt list --upgradable 2>/dev/null")
    packages = []
    for line in result["stdout"].splitlines():
        if "/" in line and "upgradable" not in line.lower():
            packages.append(line.split("/")[0])
    return JSONResponse({"packages": packages, "count": len(packages)})


@router.post("/updates/apply")
async def apply_updates(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = run_cmd("DEBIAN_FRONTEND=noninteractive apt upgrade -y")
    return JSONResponse(result)


@router.get("/services")
async def list_services(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    services = ["libvirtd", "nftables", "nexve"]
    result = {}
    for svc in services:
        r = run_cmd(f"systemctl is-active {svc}")
        result[svc] = r["stdout"]
    return JSONResponse(result)
