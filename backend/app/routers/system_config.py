from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..auth import get_current_user, api_auth
import subprocess
import os

router = APIRouter()


def run_cmd(cmd: str) -> dict:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}


@router.get("/dns")
async def get_dns(request: Request):
    user, error = api_auth(request)
    if error: return error
    r = run_cmd("cat /etc/resolv.conf")
    nameservers = []
    for line in r["stdout"].splitlines():
        if line.startswith("nameserver"):
            nameservers.append(line.split()[1])
    return JSONResponse(content={"nameservers": nameservers})


@router.post("/dns")
async def set_dns(request: Request, servers: str = Form(...)):
    user, error = api_auth(request)
    if error: return error

    server_list = [s.strip() for s in servers.split(",") if s.strip()]
    content = "# NexVE DNS Configuration\n"
    for s in server_list:
        content += f"nameserver {s}\n"

    with open("/etc/resolv.conf", "w") as f:
        f.write(content)

    return JSONResponse(content={"success": True, "nameservers": server_list})


@router.get("/ntp")
async def get_ntp(request: Request):
    user, error = api_auth(request)
    if error: return error

    # Check timedatectl
    r = run_cmd("timedatectl show --property=NTP --property=NTPServers --property=Timezone --property=LocalRTC")
    info = {}
    for line in r["stdout"].splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip()

    # Check if chrony or ntpd is running
    chrony = run_cmd("systemctl is-active chrony")
    ntpd = run_cmd("systemctl is-active ntp")

    return JSONResponse(content={
        "ntp_enabled": info.get("NTP", "no") == "yes",
        "timezone": info.get("Timezone", "UTC"),
        "ntp_service": "chrony" if chrony["stdout"] == "active" else ("ntpd" if ntpd["stdout"] == "active" else "none"),
    })


@router.post("/ntp")
async def set_ntp(request: Request, enabled: bool = Form(True), timezone: str = Form("UTC")):
    user, error = api_auth(request)
    if error: return error

    # Set timezone
    run_cmd(f"timedatectl set-timezone {timezone}")

    # Enable/disable NTP
    ntp_val = "true" if enabled else "false"
    run_cmd(f"timedatectl set-ntp {ntp_val}")

    return JSONResponse(content={"success": True})


@router.get("/timezone")
async def get_timezone(request: Request):
    user, error = api_auth(request)
    if error: return error
    r = run_cmd("timedatectl show --property=Timezone --value")
    return JSONResponse(content={"timezone": r["stdout"]})


@router.post("/timezone")
async def set_timezone(request: Request, timezone: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    run_cmd(f"timedatectl set-timezone {timezone}")
    return JSONResponse(content={"success": True})


@router.get("/hostname")
async def get_hostname(request: Request):
    user, error = api_auth(request)
    if error: return error
    r = run_cmd("hostname")
    return JSONResponse(content={"hostname": r["stdout"]})


@router.post("/hostname")
async def set_hostname(request: Request, hostname: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    run_cmd(f"hostnamectl set-hostname {hostname}")
    return JSONResponse(content={"success": True})


@router.get("/services")
async def list_services(request: Request):
    user, error = api_auth(request)
    if error: return error

    services = ["libvirtd", "nexve", "chrony", "nftables", "lxc", "ssh"]
    result = []
    for svc in services:
        r = run_cmd(f"systemctl is-active {svc}")
        result.append({
            "name": svc,
            "active": r["stdout"] == "active",
            "status": r["stdout"],
        })
    return JSONResponse(content={"services": result})


@router.post("/services/{service}/restart")
async def restart_service(request: Request, service: str):
    user, error = api_auth(request)
    if error: return error
    r = run_cmd(f"systemctl restart {service}")
    return JSONResponse(content={"success": r["success"]})


@router.post("/updates/check")
async def check_updates(request: Request):
    user, error = api_auth(request)
    if error: return error

    run_cmd("apt update -qq")
    r = run_cmd("apt list --upgradable 2>/dev/null")
    updates = []
    for line in r["stdout"].splitlines():
        if "/" in line and "upgradable" in line:
            updates.append(line.split("/")[0].split("\t")[0])

    return JSONResponse(content={"updates_available": len(updates), "packages": updates})
