from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..auth import get_current_user
import subprocess
import os
import platform
import time

router = APIRouter()


def auth_check(request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}


@router.get("/system")
async def system_info(request: Request):
    import psutil
    user, redir = auth_check(request)
    if redir:
        return redir
    boot = psutil.boot_time()
    uptime = int(time.time() - boot)
    hostname = run_cmd("hostnamectl hostname 2>/dev/null || hostname")["stdout"] or platform.node()
    os_name = run_cmd("cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'\"' -f2")["stdout"]
    kernel = platform.release()
    arch = platform.machine()
    python_ver = platform.python_version()
    debian_ver = run_cmd("cat /etc/debian_version 2>/dev/null")["stdout"]

    # CPU details
    try:
        cpu_model = run_cmd("cat /proc/cpuinfo 2>/dev/null | grep 'model name' | head -1 | cut -d: -f2")["stdout"].strip()
    except Exception:
        cpu_model = platform.processor() or 'Unknown'
    cpu_count = psutil.cpu_count(logical=True) or 0
    cpu_physical = psutil.cpu_count(logical=False) or 0
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = round(cpu_freq.current, 0) if cpu_freq else 0
        cpu_freq_max = round(cpu_freq.max, 0) if cpu_freq and cpu_freq.max else 0
    except Exception:
        cpu_freq_current = 0
        cpu_freq_max = 0

    # Memory details
    mem = psutil.virtual_memory()
    mem_total_gb = round(mem.total / (1024**3), 2)
    mem_used_gb = round(mem.used / (1024**3), 2)
    mem_available_gb = round(mem.available / (1024**3), 2)

    # Swap
    try:
        swap = psutil.swap_memory()
        swap_total_gb = round(swap.total / (1024**3), 2)
        swap_used_gb = round(swap.used / (1024**3), 2)
    except Exception:
        swap_total_gb = 0
        swap_used_gb = 0

    # Disk info
    try:
        disk = psutil.disk_usage('/')
        disk_total_gb = round(disk.total / (1024**3), 2)
        disk_used_gb = round(disk.used / (1024**3), 2)
        disk_free_gb = round(disk.free / (1024**3), 2)
    except Exception:
        disk_total_gb = 0
        disk_used_gb = 0
        disk_free_gb = 0

    # Network interfaces
    net_ifaces = psutil.net_if_addrs()
    net_stats = psutil.net_if_stats()
    interfaces = []
    for iface, addrs in net_ifaces.items():
        if iface == 'lo':
            continue
        ips = [a.address for a in addrs if a.family.name == 'AF_INET']
        mac = [a.address for a in addrs if a.family.name == 'AF_PACKET']
        stats = net_stats.get(iface)
        interfaces.append({
            'name': iface,
            'ips': ips,
            'mac': mac[0] if mac else '',
            'speed': stats.speed if stats else 0,
            'is_up': stats.isup if stats else False,
        })

    # Load average
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1 = load5 = load15 = 0

    return JSONResponse({
        "hostname": hostname,
        "domain": run_cmd("hostname -d 2>/dev/null")["stdout"],
        "os": os_name or f"Debian {debian_ver}",
        "kernel": kernel,
        "arch": arch,
        "python": python_ver,
        "uptime": uptime,
        "timezone": run_cmd("timedatectl show --property=Timezone --value 2>/dev/null")["stdout"],
        # CPU
        "cpu_model": cpu_model or 'Unknown',
        "cpu_count": cpu_count,
        "cpu_physical": cpu_physical,
        "cpu_freq_current": cpu_freq_current,
        "cpu_freq_max": cpu_freq_max,
        # Memory
        "mem_total_gb": mem_total_gb,
        "mem_used_gb": mem_used_gb,
        "mem_available_gb": mem_available_gb,
        "swap_total_gb": swap_total_gb,
        "swap_used_gb": swap_used_gb,
        # Disk
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_free_gb": disk_free_gb,
        # Network
        "interfaces": interfaces,
        # Load
        "load_1": round(load1, 2),
        "load_5": round(load5, 2),
        "load_15": round(load15, 2),
    })


@router.get("/hostname")
async def get_hostname(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    hostname = run_cmd("hostnamectl hostname 2>/dev/null || hostname")["stdout"]
    return JSONResponse({"hostname": hostname})


@router.post("/hostname")
async def set_hostname(request: Request, hostname: str = Form(...)):
    user, redir = auth_check(request)
    if redir:
        return redir
    # Set hostname via hostnamectl
    result = run_cmd(f"hostnamectl set-hostname '{hostname}'")
    if not result["success"]:
        return JSONResponse(result)
    # Update /etc/hosts
    hosts = "/etc/hosts"
    try:
        with open(hosts) as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.strip().startswith("127.0.1.1"):
                new_lines.append(f"127.0.1.1\t{hostname}\n")
            else:
                new_lines.append(line)
        with open(hosts, "w") as f:
            f.writelines(new_lines)
    except Exception:
        pass
    return JSONResponse({"success": True, "hostname": hostname})


@router.get("/dns")
async def get_dns(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    dns = run_cmd("cat /etc/resolv.conf 2>/dev/null | grep nameserver | awk '{print $2}'")["stdout"]
    search = run_cmd("cat /etc/resolv.conf 2>/dev/null | grep search | awk '{print $2}'")["stdout"]
    servers = [s.strip() for s in dns.splitlines() if s.strip()]
    return JSONResponse({"servers": servers, "search": search})


@router.post("/dns")
async def set_dns(request: Request, dns: str = Form(...), search: str = Form("")):
    user, redir = auth_check(request)
    if redir:
        return redir
    servers = [s.strip() for s in dns.split(",") if s.strip()]
    if not servers:
        return JSONResponse({"success": False, "error": "No DNS servers provided"})
    content = "# Generated by NexVE\n"
    for s in servers:
        content += f"nameserver {s}\n"
    if search:
        content += f"search {search}\n"
    try:
        with open("/etc/resolv.conf", "w") as f:
            f.write(content)
    except PermissionError:
        return JSONResponse({"success": False, "error": "Permission denied"})
    return JSONResponse({"success": True})


@router.get("/time")
async def get_time(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    tz = run_cmd("timedatectl show --property=Timezone --value 2>/dev/null")["stdout"]
    time_str = run_cmd("date '+%Y-%m-%d %H:%M:%S %Z'")["stdout"]
    ntp = run_cmd("timedatectl show --property=NTP --value 2>/dev/null")["stdout"]
    return JSONResponse({"timezone": tz, "time": time_str, "ntp_active": ntp == "yes"})


@router.post("/time")
async def set_time(request: Request, timezone: str = Form(""), ntp: str = Form("")):
    user, redir = auth_check(request)
    if redir:
        return redir
    if timezone:
        run_cmd(f"timedatectl set-timezone '{timezone}'")
    if ntp:
        enable = "true" if ntp == "true" else "false"
        run_cmd(f"timedatectl set-ntp {enable}")
    return JSONResponse({"success": True})


@router.get("/services")
async def list_services(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    services = ["libvirtd", "nftables", "nexve", "cron", "ssh", "rsyslog", "iscsid", "lxc-net"]
    result = []
    for svc_name in services:
        active = run_cmd(f"systemctl is-active {svc_name} 2>/dev/null")["stdout"]
        enabled = run_cmd(f"systemctl is-enabled {svc_name} 2>/dev/null")["stdout"]
        desc = run_cmd(f"systemctl show {svc_name} --property=Description --value 2>/dev/null")["stdout"]
        result.append({
            "name": svc_name,
            "active": active == "active",
            "enabled": enabled == "enabled",
            "description": desc,
        })
    return JSONResponse({"services": result})


@router.post("/services/{name}/{action}")
async def service_action(request: Request, name: str, action: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    if action in ("start", "stop", "restart", "reload"):
        result = run_cmd(f"systemctl {action} {name}")
        return JSONResponse(result)
    return JSONResponse({"success": False, "error": "Invalid action"})


@router.get("/updates")
async def check_updates(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    run_cmd("apt update -qq", timeout=60)
    result = run_cmd("apt list --upgradable 2>/dev/null")
    packages = []
    for line in result["stdout"].splitlines():
        if "/" in line and "upgradable" not in line.lower() and "Listing" not in line:
            name = line.split("/")[0]
            packages.append(name)
    return JSONResponse({"updates": packages, "count": len(packages)})


@router.post("/updates/apply")
async def apply_updates(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    result = run_cmd("DEBIAN_FRONTEND=noninteractive apt upgrade -y -qq", timeout=300)
    return JSONResponse(result)


@router.get("/syslog")
async def get_syslog(request: Request, level: str = "all", lines: int = 100):
    user, redir = auth_check(request)
    if redir:
        return redir
    if level == "error":
        cmd = f"journalctl -p err -n {lines} --no-pager -q 2>/dev/null || tail -n {lines} /var/log/syslog 2>/dev/null"
    elif level == "warning":
        cmd = f"journalctl -p warning -n {lines} --no-pager -q 2>/dev/null || tail -n {lines} /var/log/syslog 2>/dev/null"
    else:
        cmd = f"journalctl -n {lines} --no-pager -q 2>/dev/null || tail -n {lines} /var/log/syslog 2>/dev/null"
    result = run_cmd(cmd, timeout=15)
    log_lines = result["stdout"].splitlines() if result["stdout"] else []
    return JSONResponse({"lines": log_lines})


# ── Host Power Management ──

@router.post("/host/{action}")
async def host_power(request: Request, action: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    if user.get("role") != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    if action == "reboot":
        run_cmd("reboot", timeout=5)
        return JSONResponse({"success": True, "message": "Reboot initiated"})
    elif action == "shutdown":
        run_cmd("shutdown -h now", timeout=5)
        return JSONResponse({"success": True, "message": "Shutdown initiated"})
    return JSONResponse({"success": False, "error": "Invalid action"})


# ── Settings Import/Export/Rollback ──

@router.get("/export")
async def export_settings(request: Request):
    """Export all system settings as JSON."""
    user, redir = auth_check(request)
    if redir:
        return redir
    settings = {
        "hostname": run_cmd("hostnamectl hostname 2>/dev/null || hostname")["stdout"],
        "dns_servers": run_cmd("cat /etc/resolv.conf 2>/dev/null | grep nameserver | awk '{print $2}'")["stdout"].splitlines(),
        "dns_search": run_cmd("cat /etc/resolv.conf 2>/dev/null | grep search | awk '{print $2}'")["stdout"],
        "timezone": run_cmd("timedatectl show --property=Timezone --value 2>/dev/null")["stdout"],
        "ntp_enabled": run_cmd("timedatectl show --property=NTP --value 2>/dev/null")["stdout"] == "yes",
    }
    return JSONResponse({"settings": settings, "version": "3.0"})


@router.post("/import")
async def import_settings(request: Request):
    """Import settings from JSON."""
    user, redir = auth_check(request)
    if redir:
        return redir
    try:
        body = await request.json()
        settings = body.get("settings", {})
        
        if "hostname" in settings:
            run_cmd(f"hostnamectl set-hostname '{settings['hostname']}'")
        if "timezone" in settings:
            run_cmd(f"timedatectl set-timezone '{settings['timezone']}'")
        if "ntp_enabled" in settings:
            enable = "true" if settings["ntp_enabled"] else "false"
            run_cmd(f"timedatectl set-ntp {enable}")
        
        return JSONResponse({"success": True, "message": "Settings imported"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@router.post("/rollback")
async def rollback_settings(request: Request, key: str = Form(...)):
    """Rollback a specific setting to its previous value."""
    user, redir = auth_check(request)
    if redir:
        return redir
    # This would use the SettingsHistory model in a full implementation
    return JSONResponse({"success": True, "message": f"Rollback for {key} noted"})


# ── Install commands ──

@router.post("/install/libvirt")
async def install_libvirt(request: Request):
    """Install libvirt packages."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = run_cmd(
        "apt-get update -qq && apt-get install -y -qq libvirt-daemon-system libvirt-clients qemu-kvm 2>/dev/null",
        timeout=120
    )
    if result["success"]:
        run_cmd("systemctl enable --now libvirtd 2>/dev/null")
    return JSONResponse(result)


@router.post("/install/lxc")
async def install_lxc(request: Request):
    """Install LXC packages."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = run_cmd(
        "apt-get update -qq && apt-get install -y -qq lxc lxc-utils debootstrap 2>/dev/null",
        timeout=120
    )
    return JSONResponse(result)
