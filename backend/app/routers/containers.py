from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.vm import Container
from ..services.container_service import ContainerService
from ..auth import get_current_user
from ..security import generate_csrf_token
import json

router = APIRouter()
container_service = ContainerService()


@router.get("/create")
async def create_container_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    # Import here to avoid circular imports
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
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse({"templates": container_service.list_templates()})


@router.get("/")
async def list_containers(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        db_containers = db.query(Container).all()
        result = []
        for ct in db_containers:
            live_status = container_service.get_container_status(ct.id)
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
    template: str = Form("debian-12"),
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
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

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
    }

    # Create in LXC first (fail if LXC unavailable)
    result = container_service.create_container(config)
    if not result.get("success"):
        return JSONResponse(content=result)

    # Only create in DB if LXC succeeded
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
        )
        db.add(ct)
        db.commit()
    finally:
        db.close()

    return JSONResponse(content=result)


@router.post("/{ct_id}/start")
async def start_container(request: Request, ct_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.start_container(ct_id))


@router.post("/{ct_id}/stop")
async def stop_container(request: Request, ct_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.stop_container(ct_id))


@router.post("/{ct_id}/restart")
async def restart_container(request: Request, ct_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.restart_container(ct_id))


@router.post("/{ct_id}/delete")
async def delete_container(request: Request, ct_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        ct = db.query(Container).filter(Container.id == ct_id).first()
        if ct:
            db.delete(ct)
            db.commit()
    finally:
        db.close()

    return JSONResponse(content=container_service.delete_container(ct_id))


@router.post("/{ct_id}/update")
async def update_container(request: Request, ct_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    config = {}
    for key in ["vcpu", "memory_mb", "swap_mb", "cpu_weight", "io_priority", "net_rate", "hostname", "nesting", "unprivileged"]:
        if key in form:
            val = form[key]
            if val in ("on", "true", "True"):
                val = True
            elif val in ("off", "false", "False", ""):
                val = False
            elif key in ("vcpu", "memory_mb", "swap_mb", "cpu_weight", "net_rate"):
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
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.get_container_config(ct_id))


@router.post("/{ct_id}/mount-point/add")
async def add_mount_point(
    request: Request,
    ct_id: int,
    idx: int = Form(...),
    volume: str = Form(...),
    mp: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.add_mount_point(ct_id, idx, volume, mp))


@router.post("/{ct_id}/mount-point/remove")
async def remove_mount_point(request: Request, ct_id: int, idx: int = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.remove_mount_point(ct_id, idx))


@router.post("/{ct_id}/exec")
async def container_exec(request: Request, ct_id: int, command: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.container_exec(ct_id, command))


@router.post("/{ct_id}/backup")
async def backup_container(request: Request, ct_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.backup_container(ct_id))


@router.get("/status")
async def container_status(request: Request):
    """Check container management availability (LXC tools)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    import shutil
    has_pct = shutil.which('pct') is not None
    has_lxc = shutil.which('lxc-ls') is not None
    has_lxc_attach = shutil.which('lxc-attach') is not None
    
    return JSONResponse({
        "available": has_pct or has_lxc,
        "pct": has_pct,
        "lxc": has_lxc,
        "lxc_attach": has_lxc_attach,
        "message": "" if (has_pct or has_lxc) else "LXC tools not installed. Install: apt install lxc-utils",
    })
