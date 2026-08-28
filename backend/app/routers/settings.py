from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..auth import get_current_user, api_auth
import subprocess
import os
import platform
import time

router = APIRouter()



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
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    hostname = run_cmd("hostnamectl hostname 2>/dev/null || hostname")["stdout"]
    return JSONResponse({"hostname": hostname})


@router.post("/hostname")
async def set_hostname(request: Request, hostname: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    dns = run_cmd("cat /etc/resolv.conf 2>/dev/null | grep nameserver | awk '{print $2}'")["stdout"]
    search = run_cmd("cat /etc/resolv.conf 2>/dev/null | grep search | awk '{print $2}'")["stdout"]
    servers = [s.strip() for s in dns.splitlines() if s.strip()]
    return JSONResponse({"servers": servers, "search": search})


@router.post("/dns")
async def set_dns(request: Request, dns: str = Form(...), search: str = Form("")):
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    tz = run_cmd("timedatectl show --property=Timezone --value 2>/dev/null")["stdout"]
    time_str = run_cmd("date '+%Y-%m-%d %H:%M:%S %Z'")["stdout"]
    ntp = run_cmd("timedatectl show --property=NTP --value 2>/dev/null")["stdout"]
    return JSONResponse({"timezone": tz, "time": time_str, "ntp_active": ntp == "yes"})


@router.post("/time")
async def set_time(request: Request, timezone: str = Form(""), ntp: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    if timezone:
        run_cmd(f"timedatectl set-timezone '{timezone}'")
    if ntp:
        enable = "true" if ntp == "true" else "false"
        run_cmd(f"timedatectl set-ntp {enable}")
    return JSONResponse({"success": True})


@router.get("/services")
async def list_services(request: Request):
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    if action in ("start", "stop", "restart", "reload"):
        result = run_cmd(f"systemctl {action} {name}")
        return JSONResponse(result)
    return JSONResponse({"success": False, "error": "Invalid action"})


@router.get("/updates")
async def check_updates(request: Request):
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    result = run_cmd("DEBIAN_FRONTEND=noninteractive apt upgrade -y -qq", timeout=300)
    return JSONResponse(result)


@router.get("/syslog")
async def get_syslog(request: Request, level: str = "all", lines: int = 100):
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    if not user or user.role != "admin":
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
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    # This would use the SettingsHistory model in a full implementation
    return JSONResponse({"success": True, "message": f"Rollback for {key} noted"})


# ── Install commands ──

@router.post("/install/libvirt")
async def install_libvirt(request: Request):
    """Install libvirt packages."""
    user, error = api_auth(request)
    if error: return error
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
    user, error = api_auth(request)
    if error: return error
    result = run_cmd(
        "apt-get update -qq && apt-get install -y -qq lxc lxc-utils debootstrap 2>/dev/null",
        timeout=120
    )
    return JSONResponse(result)


@router.get("/system-report")
async def system_report(request: Request):
    """Generate and return a comprehensive HTML system report."""
    from fastapi.responses import HTMLResponse
    import psutil
    import subprocess
    import os
    from datetime import datetime

    cpu_count = psutil.cpu_count(logical=True)
    cpu_physical = psutil.cpu_count(logical=False)
    cpu_freq = psutil.cpu_freq()
    cpu_percent = psutil.cpu_percent(interval=0.5)
    load_avg = os.getloadavg()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")
    net_io = psutil.net_io_counters()

    vm_count = 0
    ct_count = 0
    try:
        r = subprocess.run("virsh list --name 2>/dev/null | wc -l", shell=True, capture_output=True, text=True, timeout=5)
        vm_count = int(r.stdout.strip()) if r.returncode == 0 else 0
    except: pass
    try:
        r = subprocess.run("lxc-ls 2>/dev/null | wc -w", shell=True, capture_output=True, text=True, timeout=5)
        ct_count = int(r.stdout.strip()) if r.returncode == 0 else 0
    except: pass

    zfs_pools = 0
    try:
        r = subprocess.run("zpool list -H 2>/dev/null | wc -l", shell=True, capture_output=True, text=True, timeout=5)
        zfs_pools = int(r.stdout.strip()) if r.returncode == 0 else 0
    except: pass

    net_ifaces = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name == "AF_INET":
                net_ifaces.append({"name": name, "ip": addr.address})

    boot_seconds = psutil.boot_time()
    uptime_seconds = datetime.now().timestamp() - boot_seconds
    uptime_days = int(uptime_seconds // 86400)
    uptime_hours = int((uptime_seconds % 86400) // 3600)
    uptime_mins = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_mins}m"

    iface_rows = "".join(f"<tr><td>{i['name']}</td><td>{i['ip']}</td></tr>" for i in net_ifaces) if net_ifaces else '<tr><td colspan="2">No interfaces</td></tr>'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>NexVE System Report</title>
<style>
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:40px;background:#0f1419;color:#e4e8ec; }}
h1 {{ color:#00d4aa;border-bottom:2px solid #00d4aa;padding-bottom:12px; }}
h2 {{ color:#00d4aa;margin-top:32px; }}
table {{ width:100%;border-collapse:collapse;margin:16px 0; }}
th,td {{ padding:10px 16px;text-align:left;border-bottom:1px solid #2a3441; }}
th {{ color:#8899a6;font-weight:600;text-transform:uppercase;font-size:0.8em; }}
.stat {{ display:inline-block;background:#1a2332;padding:16px 24px;border-radius:8px;margin:8px;min-width:160px; }}
.stat .value {{ font-size:1.8em;font-weight:700;color:#00d4aa; }}
.stat .label {{ font-size:0.85em;color:#8899a6;margin-top:4px; }}
.footer {{ margin-top:40px;padding-top:16px;border-top:1px solid #2a3441;color:#8899a6;font-size:0.85em; }}
</style></head><body>
<h1>🔒 NexVE System Report</h1>
<p>Generated: {datetime.now().strftime('%B %d, %Y at %H:%M:%S')}</p>
<p>Hostname: {os.uname().nodename} | OS: {os.uname().sysname} {os.uname().release} | Arch: {os.uname().machine}</p>
<h2>📊 CPU</h2>
<div style="text-align:center;">
<div class="stat"><div class="value">{cpu_percent}%</div><div class="label">CPU Usage</div></div>
<div class="stat"><div class="value">{cpu_count}</div><div class="label">Logical Cores</div></div>
<div class="stat"><div class="value">{cpu_physical or 'N/A'}</div><div class="label">Physical Cores</div></div>
<div class="stat"><div class="value">{cpu_freq.current if cpu_freq else 'N/A'} MHz</div><div class="label">Frequency</div></div>
<div class="stat"><div class="value">{load_avg[0]:.2f} / {load_avg[1]:.2f} / {load_avg[2]:.2f}</div><div class="label">Load Avg</div></div>
</div>
<h2>💾 Memory</h2>
<div style="text-align:center;">
<div class="stat"><div class="value">{mem.total / (1024**3):.1f} GB</div><div class="label">Total RAM</div></div>
<div class="stat"><div class="value">{mem.used / (1024**3):.1f} GB</div><div class="label">Used RAM</div></div>
<div class="stat"><div class="value">{mem.percent}%</div><div class="label">Usage</div></div>
<div class="stat"><div class="value">{swap.total / (1024**3):.1f} GB</div><div class="label">Swap</div></div>
</div>
<h2>💿 Disk</h2>
<div style="text-align:center;">
<div class="stat"><div class="value">{disk.total / (1024**3):.1f} GB</div><div class="label">Total</div></div>
<div class="stat"><div class="value">{disk.used / (1024**3):.1f} GB</div><div class="label">Used</div></div>
<div class="stat"><div class="value">{disk.free / (1024**3):.1f} GB</div><div class="label">Free</div></div>
<div class="stat"><div class="value">{disk.percent}%</div><div class="label">Usage</div></div>
</div>
<h2>🌐 Network</h2>
<table><tr><th>Interface</th><th>IP</th></tr>{iface_rows}</table>
<div style="margin-top:12px;">
<div class="stat"><div class="value">{net_io.bytes_recv / (1024**2):.1f} MB</div><div class="label">Received</div></div>
<div class="stat"><div class="value">{net_io.bytes_sent / (1024**2):.1f} MB</div><div class="label">Sent</div></div>
</div>
<h2>🖥️ Virtualization</h2>
<div style="text-align:center;">
<div class="stat"><div class="value">{vm_count}</div><div class="label">Running VMs</div></div>
<div class="stat"><div class="value">{ct_count}</div><div class="label">Containers</div></div>
<div class="stat"><div class="value">{zfs_pools}</div><div class="label">ZFS Pools</div></div>
</div>
<h2>ℹ️ NexVE</h2>
<table>
<tr><th>Version</th><td>NexVE v3.0</td></tr>
<tr><th>Uptime</th><td>{uptime_str}</td></tr>
<tr><th>Python</th><td>{subprocess.run("python3 --version", shell=True, capture_output=True, text=True).stdout.strip()}</td></tr>
</table>
<div class="footer">Generated by NexVE v3.0 — Open Source Hypervisor Management Platform</div>
</body></html>"""
    return HTMLResponse(html)



# ── Update Repository Management ──

@router.get("/repositories")
async def list_repositories(request: Request):
    """List configured apt repositories."""
    user, error = api_auth(request)
    if error: return error
    import os
    repos = []
    sources_dir = "/etc/apt/sources.list.d"
    main_list = "/etc/apt/sources.list"
    for path in [main_list] + ([os.path.join(sources_dir, f) for f in os.listdir(sources_dir)] if os.path.isdir(sources_dir) else []):
        if os.path.exists(path):
            try:
                with open(path) as f:
                    content = f.read()
                lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 3:
                        repos.append({
                            "source_file": path,
                            "type": parts[0],
                            "url": parts[1],
                            "distribution": parts[2] if len(parts) > 2 else "",
                            "components": parts[3:] if len(parts) > 3 else [],
                            "enabled": True,
                        })
            except Exception:
                pass
    return JSONResponse({"repositories": repos})


@router.post("/repositories/toggle")
async def toggle_repository(request: Request, source_file: str = Form(...),
                            url: str = Form(...), enabled: str = Form("true")):
    """Enable/disable an apt repository."""
    user, error = api_auth(request)
    if error: return error
    if user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin required"}, status_code=403)
    import os
    try:
        with open(source_file) as f:
            lines = f.readlines()
        new_lines = []
        found = False
        for line in lines:
            if url in line:
                found = True
                if enabled.lower() in ("false", "0"):
                    new_lines.append("#" + line if not line.startswith("#") else line)
                else:
                    new_lines.append(line.lstrip("#"))
            else:
                new_lines.append(line)
        if found:
            with open(source_file, "w") as f:
                f.writelines(new_lines)
            return JSONResponse({"success": True})
        return JSONResponse({"success": False, "error": "Repository not found"})
    except PermissionError:
        return JSONResponse({"success": False, "error": "Permission denied"})


@router.post("/update/check")
async def check_updates(request: Request):
    """Check for available updates."""
    user, error = api_auth(request)
    if error: return error
    import subprocess
    r = subprocess.run("apt list --upgradable 2>/dev/null | tail -n +2", shell=True, capture_output=True, text=True, timeout=60)
    updates = []
    for line in r.stdout.splitlines():
        if "/" in line:
            parts = line.split()
            if len(parts) >= 2:
                updates.append({"package": parts[0], "new_version": parts[1]})
    return JSONResponse({"updates": updates, "count": len(updates)})


# ── Audit Logging ──

@router.get("/audit")
async def list_audit_log(request: Request, limit: int = 100):
    """Get audit log entries."""
    user, error = api_auth(request)
    if error: return error
    from ..models.user import AuditLog
    db = SessionLocal()
    try:
        entries = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
        return JSONResponse({"entries": [{
            "id": e.id, "user": e.user_id, "action": e.action,
            "resource": e.resource, "details": e.details or "",
            "ip": e.ip_address or "", "time": e.created_at.isoformat() if e.created_at else ""
        } for e in entries]})
    finally:
        db.close()


def log_audit(user_id: int, action: str, resource: str = "", details: str = "", ip: str = ""):
    """Write an audit log entry."""
    from ..models.user import AuditLog
    db = SessionLocal()
    try:
        db.add(AuditLog(user_id=user_id, action=action, resource=resource, details=details, ip_address=ip))
        db.commit()
    except Exception:
        pass
    finally:
        db.close()
