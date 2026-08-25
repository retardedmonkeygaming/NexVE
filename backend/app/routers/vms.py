from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.vm import VM
from ..services.vm_service import VMService
from ..auth import get_current_user

router = APIRouter()
vm_service = VMService()


@router.get("/")
async def list_vms(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content={"vms": vm_service.get_all_vms(SessionLocal())})


@router.get("/{vm_id}")
async def get_vm(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        vm = vm_service.get_vm(db, vm_id)
        if not vm:
            return JSONResponse(content={"error": "VM not found"}, status_code=404)
        return JSONResponse(content=vm)
    finally:
        db.close()


@router.post("/create")
async def create_vm(
    request: Request,
    name: str = Form(...),
    vcpu: int = Form(2),
    memory_mb: int = Form(2048),
    disk_gb: int = Form(50),
    os_type: str = Form("linux"),
    cpu_type: str = Form("host"),
    machine_type: str = Form("q35"),
    bios_type: str = Form("seabios"),
    boot_order: str = Form("c"),
    disk_interface: str = Form("virtio"),
    serial_console: bool = Form(False),
    agent_enabled: bool = Form(True),
    balloon: bool = Form(False),
    notes: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        result = vm_service.create_vm(db, {
            "name": name,
            "vcpu": vcpu,
            "memory_mb": memory_mb,
            "disk_gb": disk_gb,
            "os_type": os_type,
            "cpu_type": cpu_type,
            "machine_type": machine_type,
            "bios_type": bios_type,
            "boot_order": boot_order,
            "disk_interface": disk_interface,
            "serial_console": serial_console,
            "agent_enabled": agent_enabled,
            "balloon": balloon,
            "notes": notes,
        })
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{vm_id}/update")
async def update_vm(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    config = {}
    updatable = [
        "name", "vcpu", "cpu_type", "memory_mb", "disk_gb",
        "disk_interface", "os_type", "machine_type", "bios_type",
        "boot_order", "notes", "serial_console", "agent_enabled",
        "balloon", "hotplug_cpu", "hotplug_ram",
    ]
    for key in updatable:
        if key in form:
            val = form[key]
            if val in ("on", "true", "True", "1"):
                val = True
            elif val in ("off", "false", "False", "0", ""):
                val = False
            else:
                try:
                    val = int(val)
                except ValueError:
                    pass
            config[key] = val

    db = SessionLocal()
    try:
        result = vm_service.update_vm(db, vm_id, config)
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{vm_id}/delete")
async def delete_vm(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        result = vm_service.delete_vm(db, vm_id)
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{vm_id}/start")
async def start_vm(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.start_vm(db, vm_id))
    finally:
        db.close()


@router.post("/{vm_id}/stop")
async def stop_vm(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.stop_vm(db, vm_id))
    finally:
        db.close()


@router.post("/{vm_id}/restart")
async def restart_vm(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.restart_vm(db, vm_id))
    finally:
        db.close()


@router.post("/{vm_id}/clone")
async def clone_vm(
    request: Request,
    vm_id: int,
    new_name: str = Form(...),
    linked: bool = Form(False),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.clone_vm(db, vm_id, new_name, linked))
    finally:
        db.close()


@router.post("/{vm_id}/resize-disk")
async def resize_disk(
    request: Request,
    vm_id: int,
    new_size_gb: int = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.resize_disk(db, vm_id, new_size_gb))
    finally:
        db.close()


@router.get("/{vm_id}/config")
async def vm_config(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        vm = vm_service.get_vm(db, vm_id)
        if not vm:
            return JSONResponse(content={"error": "VM not found"}, status_code=404)
        config = vm_service.get_vm_config(vm["name"])
        return JSONResponse(content=config)
    finally:
        db.close()


@router.post("/{vm_id}/snapshot/create")
async def create_snapshot(
    request: Request,
    vm_id: int,
    name: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.create_snapshot(db, vm_id, name))
    finally:
        db.close()


@router.get("/{vm_id}/snapshots")
async def list_snapshots(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content={"snapshots": vm_service.list_snapshots(vm_id, db)})
    finally:
        db.close()


@router.post("/{vm_id}/snapshot/{snap_name}/restore")
async def restore_snapshot(request: Request, vm_id: int, snap_name: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.restore_snapshot(vm_id, snap_name, db))
    finally:
        db.close()


@router.post("/{vm_id}/snapshot/{snap_name}/delete")
async def delete_snapshot(request: Request, vm_id: int, snap_name: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.delete_snapshot(vm_id, snap_name, db))
    finally:
        db.close()
