from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.vm import VM
from ..services.vm_service import VMService
from ..auth import get_current_user

router = APIRouter()
vm_service = VMService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/")
async def list_vms(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(content={"vms": vm_service.get_all_vms(SessionLocal())})


@router.get("/{vm_id}")
async def get_vm(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
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
    user, redir = auth_check(request)
    if redir:
        return redir

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
    user, redir = auth_check(request)
    if redir:
        return redir

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
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.delete_vm(db, vm_id)
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{vm_id}/start")
async def start_vm(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.start_vm(db, vm_id))
    finally:
        db.close()


@router.post("/{vm_id}/stop")
async def stop_vm(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.stop_vm(db, vm_id))
    finally:
        db.close()


@router.post("/{vm_id}/restart")
async def restart_vm(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
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
    user, redir = auth_check(request)
    if redir:
        return redir
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
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.resize_disk(db, vm_id, new_size_gb))
    finally:
        db.close()


@router.get("/{vm_id}/config")
async def vm_config(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
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
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.create_snapshot(db, vm_id, name))
    finally:
        db.close()


@router.get("/{vm_id}/snapshots")
async def list_snapshots(request: Request, vm_id: int):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        return JSONResponse(content={"snapshots": vm_service.list_snapshots(vm_id, db)})
    finally:
        db.close()


@router.post("/{vm_id}/snapshot/{snap_name}/restore")
async def restore_snapshot(request: Request, vm_id: int, snap_name: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.restore_snapshot(vm_id, snap_name, db))
    finally:
        db.close()


@router.post("/{vm_id}/snapshot/{snap_name}/delete")
async def delete_snapshot(request: Request, vm_id: int, snap_name: str):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        return JSONResponse(content=vm_service.delete_snapshot(vm_id, snap_name, db))
    finally:
        db.close()


# ── Hot-add CPU ──

@router.post("/{vm_id}/hotplug/cpu")
async def hotplug_cpu(request: Request, vm_id: int, vcpus: int = Form(...)):
    """Hot-add CPU cores to a running VM."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.hotplug_cpu(db, vm_id, vcpus)
        return JSONResponse(content=result)
    finally:
        db.close()


# ── Hot-add RAM ──

@router.post("/{vm_id}/hotplug/ram")
async def hotplug_ram(request: Request, vm_id: int, memory_mb: int = Form(...)):
    """Hot-add memory to a running VM."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.hotplug_ram(db, vm_id, memory_mb)
        return JSONResponse(content=result)
    finally:
        db.close()


# ── Memory Ballooning ──

@router.post("/{vm_id}/balloon")
async def set_balloon(request: Request, vm_id: int, enabled: bool = Form(True)):
    """Enable/disable memory ballooning."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.update_vm(db, vm_id, {"balloon": enabled})
        return JSONResponse(content=result)
    finally:
        db.close()


# ── Import OVF/OVA ──

@router.post("/import")
async def import_ovf(request: Request, file: UploadFile = File(...)):
    """Import a VM from OVF/OVA file."""
    user, redir = auth_check(request)
    if redir:
        return redir

    import os
    import tempfile

    upload_dir = "/opt/nexve/data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, file.filename)

    with open(filepath, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    result = vm_service.import_ovf(filepath)
    return JSONResponse(content=result)


# ── Move Disk Between Storage Backends ──

@router.post("/{vm_id}/move-disk")
async def move_vm_disk(
    request: Request,
    vm_id: int,
    disk_index: int = Form(0),
    target_storage: str = Form(...),
):
    """Move a VM disk to a different storage backend."""
    user, redir = auth_check(request)
    if redir:
        return redir

    from ..services.storage_service import StorageService
    storage_svc = StorageService()

    db = SessionLocal()
    try:
        vm = vm_service.get_vm(db, vm_id)
        if not vm:
            return JSONResponse(content={"error": "VM not found"}, status_code=404)
        result = storage_svc.migrate_disk(vm["name"], disk_index, target_storage)
        return JSONResponse(content=result)
    finally:
        db.close()


# ── PCI/e GPU Passthrough ──

@router.get("/passthrough/gpu")
async def list_gpu_passthrough(request: Request):
    """List available GPUs for passthrough."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = vm_service.list_pci_devices(device_class="0300")
    return JSONResponse(content={"devices": result})


@router.get("/passthrough/usb")
async def list_usb_passthrough(request: Request):
    """List available USB devices for passthrough."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = vm_service.list_usb_devices()
    return JSONResponse(content={"devices": result})


@router.post("/{vm_id}/passthrough/pci")
async def attach_pci(
    request: Request,
    vm_id: int,
    pci_addr: str = Form(...),
):
    """Attach a PCI/e device to a VM."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.attach_pci_device(db, vm_id, pci_addr)
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{vm_id}/passthrough/usb")
async def attach_usb(
    request: Request,
    vm_id: int,
    vendor_id: str = Form(...),
    product_id: str = Form(...),
):
    """Attach a USB device to a VM."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.attach_usb_device(db, vm_id, vendor_id, product_id)
        return JSONResponse(content=result)
    finally:
        db.close()


@router.post("/{vm_id}/passthrough/detach")
async def detach_passthrough(
    request: Request,
    vm_id: int,
    device_addr: str = Form(...),
):
    """Detach a passthrough device from a VM."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.detach_pci_device(db, vm_id, device_addr)
        return JSONResponse(content=result)
    finally:
        db.close()


# ── Bulk Actions ──

@router.post("/bulk/start")
async def bulk_start(request: Request):
    """Start multiple VMs."""
    user, redir = auth_check(request)
    if redir:
        return redir
    form = await request.form()
    vm_ids_str = form.get("vm_ids", "")
    vm_ids = [int(x) for x in vm_ids_str.split(",") if x.strip().isdigit()]

    results = []
    db = SessionLocal()
    try:
        for vm_id in vm_ids:
            result = vm_service.start_vm(db, vm_id)
            results.append({"vm_id": vm_id, **result})
    finally:
        db.close()
    return JSONResponse(content={"results": results})


@router.post("/bulk/stop")
async def bulk_stop(request: Request):
    """Stop multiple VMs."""
    user, redir = auth_check(request)
    if redir:
        return redir
    form = await request.form()
    vm_ids_str = form.get("vm_ids", "")
    vm_ids = [int(x) for x in vm_ids_str.split(",") if x.strip().isdigit()]

    results = []
    db = SessionLocal()
    try:
        for vm_id in vm_ids:
            result = vm_service.stop_vm(db, vm_id)
            results.append({"vm_id": vm_id, **result})
    finally:
        db.close()
    return JSONResponse(content={"results": results})


@router.post("/bulk/delete")
async def bulk_delete(request: Request):
    """Delete multiple VMs."""
    user, redir = auth_check(request)
    if redir:
        return redir
    form = await request.form()
    vm_ids_str = form.get("vm_ids", "")
    vm_ids = [int(x) for x in vm_ids_str.split(",") if x.strip().isdigit()]

    results = []
    db = SessionLocal()
    try:
        for vm_id in vm_ids:
            result = vm_service.delete_vm(db, vm_id)
            results.append({"vm_id": vm_id, **result})
    finally:
        db.close()
    return JSONResponse(content={"results": results})


# ── Convert to Template ──

@router.post("/{vm_id}/convert-template")
async def convert_to_template(request: Request, vm_id: int):
    """Convert a VM to a template."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        result = vm_service.convert_to_template(db, vm_id)
        return JSONResponse(content=result)
    finally:
        db.close()


# ── VM Metrics ──

@router.get("/{vm_id}/metrics")
async def vm_metrics(request: Request, vm_id: int):
    """Get per-VM resource usage metrics."""
    user, redir = auth_check(request)
    if redir:
        return redir
    from ..services.monitor_service import MonitorService
    monitor = MonitorService()
    db = SessionLocal()
    try:
        vm = vm_service.get_vm(db, vm_id)
        if not vm:
            return JSONResponse(content={"error": "VM not found"}, status_code=404)
        metrics = monitor.get_vm_metrics(vm["name"])
        return JSONResponse(content=metrics)
    finally:
        db.close()


# ── VM Status (for libvirt check) ──

@router.get("/status")
async def vm_status(request: Request):
    """Check VM management availability (libvirt connection)."""
    user, redir = auth_check(request)
    if redir:
        return redir
    
    import shutil
    has_libvirt = shutil.which('virsh') is not None
    
    libvirt_connected = False
    if has_libvirt:
        try:
            import libvirt
            conn = libvirt.open('qemu:///system')
            if conn:
                libvirt_connected = True
                conn.close()
        except Exception:
            pass
    
    return JSONResponse({
        "available": has_libvirt and libvirt_connected,
        "libvirt_installed": has_libvirt,
        "libvirt_connected": libvirt_connected,
        "message": "" if libvirt_connected else "libvirt not available. Install: apt install libvirt-daemon-system libvirt-clients",
    })
