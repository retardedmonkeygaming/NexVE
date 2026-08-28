from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.vm import Container
from ..services.container_service import ContainerService
from ..auth import get_current_user, api_auth
from ..task_utils import log_task
from ..security import generate_csrf_token
import json

router = APIRouter()
container_service = ContainerService()


@router.get("/create")
async def create_container_page(request: Request):
    user, error = api_auth(request)
    if error: return error
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    from fastapi.templating import Jinja2Templates
    import os
    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../templates")
    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    return templates.TemplateResponse(request=request, name="containers.html", context={
        "user": user, "csrf_token": csrf, "page": "containers",
        "hostname": os.uname().nodename, "show_create": True
    })


@router.get("/templates")
async def list_templates(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"templates": container_service.list_templates()})


@router.get("/system-info")
async def system_info(request: Request):
    """Get LXC system information for diagnostics."""
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(content=container_service.get_system_info())


@router.get("/")
async def list_containers(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        db_containers = db.query(Container).all()
        result = []
        for ct in db_containers:
            live_status = container_service.get_container_status(ct.id)
            # If lxc-info returned unknown, fall back to DB status
            if live_status == "unknown" and ct.status:
                live_status = ct.status
            result.append({
                "id": ct.id,
                "name": ct.name,
                "status": live_status,
                "vcpu": ct.vcpu,
                "memory_mb": ct.memory_mb,
                "swap_mb": ct.swap_mb,
                "disk_gb": ct.disk_gb,
                "template": ct.template,
                "ip_address": ct.ip_address,
                "hostname": ct.hostname,
                "unprivileged": ct.unprivileged,
                "nesting": ct.nesting,
                "mount_points": ct.mount_points,
                "cpu_weight": ct.cpu_weight,
                "io_priority": ct.io_priority,
                "net_rate": ct.net_rate,
                "startup_order": ct.startup_order,
                "shutdown_order": ct.shutdown_order,
                "notes": ct.notes or "",
                "created_at": ct.created_at.isoformat() if ct.created_at else None,
            })
        return JSONResponse(content={"containers": result})
    finally:
        db.close()


@router.post("/create")
async def create_container(
    request: Request,
    name: str = Form(...),
    ct_id: int = Form(1000),
    hostname: str = Form(""),
    vcpu: int = Form(1),
    memory_mb: int = Form(512),
    swap_mb: int = Form(512),
    disk_gb: int = Form(8),
    template: str = Form("debian/bookworm"),
    ip_address: str = Form(""),
    unprivileged: bool = Form(True),
    nesting: bool = Form(False),
    mount_points: str = Form(""),
    cpu_weight: int = Form(100),
    io_priority: str = Form("normal"),
    net_rate: str = Form(""),
    startup_order: int = Form(0),
    shutdown_order: int = Form(0),
    notes: str = Form(""),
    dns_servers: str = Form(""),
    gateway: str = Form(""),
    mac_address: str = Form(""),
    mtu: int = Form(1500),
    cpu_quota: str = Form(""),
    cpu_period: int = Form(100000),
    cpu_nice: int = Form(0),
    ssh_keys: str = Form(""),
    seccomp_profile: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error

    config = {
        "name": name,
        "ct_id": ct_id,
        "hostname": hostname or name,
        "vcpu": vcpu,
        "memory_mb": memory_mb,
        "swap_mb": swap_mb,
        "disk_gb": disk_gb,
        "template": template,
        "ip_address": ip_address,
        "unprivileged": unprivileged,
        "nesting": nesting,
        "mount_points": mount_points,
        "cpu_weight": cpu_weight,
        "io_priority": io_priority,
        "net_rate": int(net_rate) if net_rate else None,
        "startup_order": startup_order,
        "shutdown_order": shutdown_order,
        "dns_servers": dns_servers,
        "gateway": gateway,
        "mac_address": mac_address,
        "mtu": mtu,
        "cpu_quota": int(cpu_quota) if cpu_quota else None,
        "cpu_period": cpu_period,
        "cpu_nice": cpu_nice,
        "ssh_keys": ssh_keys,
        "seccomp_profile": seccomp_profile,
    }

    result = container_service.create_container(config)
    if not result.get("success"):
        return JSONResponse(content=result)

    db = SessionLocal()
    try:
        ct = Container(
            id=ct_id,
            name=name,
            vcpu=vcpu,
            memory_mb=memory_mb,
            swap_mb=swap_mb,
            disk_gb=disk_gb,
            template=template,
            ip_address=ip_address or None,
            hostname=hostname or name,
            unprivileged=unprivileged,
            nesting=nesting,
            mount_points=mount_points,
            cpu_weight=cpu_weight,
            io_priority=io_priority,
            net_rate=int(net_rate) if net_rate else None,
            startup_order=startup_order,
            shutdown_order=shutdown_order,
            notes=notes,
            dns_servers=dns_servers or None,
            gateway=gateway or None,
            mac_address=mac_address or None,
            mtu=mtu,
            cpu_quota=int(cpu_quota) if cpu_quota else None,
            cpu_period=cpu_period,
            cpu_nice=cpu_nice,
            ssh_keys=ssh_keys or None,
            seccomp_profile=seccomp_profile or None,
        )
        db.add(ct)
        db.commit()
    finally:
        db.close()

    return JSONResponse(content=result)


@router.post("/{ct_id}/start")
async def start_container(request: Request, ct_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        ct = db.query(Container).filter(Container.id == ct_id).first()
        name = ct.name if ct else str(ct_id)
        result = container_service.start_container_by_name(name)
        if result.get("success") and ct:
            ct.status = "running"
            db.commit()
        log_task(user.id, user.username, "ct.start", "container", name, "completed" if result.get("success") else "failed")
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{ct_id}/stop")
async def stop_container(request: Request, ct_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        ct = db.query(Container).filter(Container.id == ct_id).first()
        name = ct.name if ct else str(ct_id)
        result = container_service.stop_container_by_name(name)
        if result.get("success") and ct:
            ct.status = "stopped"
            db.commit()
        log_task(user.id, user.username, "ct.stop", "container", name, "completed" if result.get("success") else "failed")
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{ct_id}/restart")
async def restart_container(request: Request, ct_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        ct = db.query(Container).filter(Container.id == ct_id).first()
        name = ct.name if ct else str(ct_id)
    finally:
        db.close()
    result = container_service.restart_container_by_name(name)
    log_task(user.id, user.username, "ct.restart", "container", name, "completed" if result.get("success") else "failed")
    return JSONResponse(content=result)


@router.post("/{ct_id}/delete")
async def delete_container(request: Request, ct_id: int):
    user, error = api_auth(request)
    if error: return error

    # Look up container name from DB first
    db = SessionLocal()
    try:
        ct = db.query(Container).filter(Container.id == ct_id).first()
        if not ct:
            return JSONResponse(content={"success": False, "error": "Container not found"}, status_code=404)
        name = ct.name
    finally:
        db.close()

    # Actually destroy the container on the system using its name
    result = container_service.delete_container_by_name(name)

    # Only remove from DB if destruction succeeded
    if result.get("success"):
        db = SessionLocal()
        try:
            ct = db.query(Container).filter(Container.id == ct_id).first()
            if ct:
                db.delete(ct)
                db.commit()
        finally:
            db.close()
    else:
        return JSONResponse(content=result, status_code=500)

    log_task(user.id, user.username, "ct.delete", "container", name, "completed" if result.get("success") else "failed")
    return JSONResponse(content=result)


@router.post("/{ct_id}/update")
async def update_container(request: Request, ct_id: int):
    user, error = api_auth(request)
    if error: return error

    form = await request.form()
    config = {}
    for key in ["vcpu", "memory_mb", "swap_mb", "cpu_weight", "io_priority", "net_rate", "hostname", "nesting", "unprivileged",
               "dns_servers", "gateway", "mac_address", "mtu", "cpu_quota", "cpu_period", "cpu_nice", "ssh_keys", "seccomp_profile"]:
        if key in form:
            val = form[key]
            if val in ("on", "true", "True"):
                val = True
            elif val in ("off", "false", "False", ""):
                val = False
            elif key in ("vcpu", "memory_mb", "swap_mb", "cpu_weight", "net_rate", "mtu", "cpu_period", "cpu_nice"):
                try:
                    val = int(val) if val else None
                except ValueError:
                    pass
            elif key == "cpu_quota":
                try:
                    val = int(val) if val else None
                except ValueError:
                    pass
            config[key] = val

    db = SessionLocal()
    try:
        ct = db.query(Container).filter(Container.id == ct_id).first()
        if ct:
            for k, v in config.items():
                if hasattr(ct, k):
                    setattr(ct, k, v)
            db.commit()
    finally:
        db.close()

    result = container_service.update_container(ct_id, config)
    return JSONResponse(content=result)


@router.get("/{ct_id}/config")
async def container_config(request: Request, ct_id: int):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(content=container_service.get_container_config(ct_id))


@router.post("/{ct_id}/mount-point/add")
async def add_mount_point(
    request: Request,
    ct_id: int,
    idx: int = Form(...),
    volume: str = Form(...),
    mp: str = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(content=container_service.add_mount_point(ct_id, idx, volume, mp))


@router.post("/{ct_id}/mount-point/remove")
async def remove_mount_point(request: Request, ct_id: int, idx: int = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(content=container_service.remove_mount_point(ct_id, idx))


@router.post("/{ct_id}/exec")
async def container_exec(request: Request, ct_id: int, command: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(content=container_service.container_exec(ct_id, command))


@router.post("/{ct_id}/backup")
async def backup_container(request: Request, ct_id: int):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(content=container_service.backup_container(ct_id))


@router.get("/status")
async def container_status(request: Request):
    """Check LXC container management availability with detailed diagnostics."""
    user, error = api_auth(request)
    if error: return error
    info = container_service.get_system_info()
    return JSONResponse(content=info)
