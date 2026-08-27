from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime
from ..database import SessionLocal
from ..models.vm import VM, Container, BackupSchedule
from ..services.vm_service import VMService
from ..services.backup_service import BackupService
from ..services.container_service import ContainerService
from ..auth import get_current_user
import subprocess

router = APIRouter()
vm_service = VMService()
container_service = ContainerService()
backup_svc = BackupService()


@router.get("/schedules")
async def list_schedules(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    try:
        schedules = db.query(BackupSchedule).all()
        return JSONResponse(content={"schedules": [
            {
                "id": s.id,
                "name": s.name,
                "target_type": s.target_type,
                "target_id": s.target_id,
                "cron_expr": s.cron_expr,
                "retention_days": s.retention_days,
                "max_backups": s.max_backups,
                "enabled": s.enabled,
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in schedules
        ]})
    finally:
        db.close()


@router.post("/schedules/create")
async def create_schedule(
    request: Request,
    name: str = Form(...),
    target_type: str = Form(...),
    target_id: int = Form(...),
    cron_expr: str = Form("0 2 * * *"),
    retention_days: int = Form(30),
    max_backups: int = Form(7),
    enabled: bool = Form(True),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        schedule = BackupSchedule(
            name=name,
            target_type=target_type,
            target_id=target_id,
            cron_expr=cron_expr,
            retention_days=retention_days,
            max_backups=max_backups,
            enabled=enabled,
        )
        db.add(schedule)
        db.commit()

        # Install cron job
        _install_cron(schedule)

        return JSONResponse(content={"success": True, "id": schedule.id})
    finally:
        db.close()


@router.post("/schedules/{schedule_id}/toggle")
async def toggle_schedule(request: Request, schedule_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        schedule = db.query(BackupSchedule).filter(BackupSchedule.id == schedule_id).first()
        if not schedule:
            return JSONResponse(content={"error": "Not found"}, status_code=404)
        schedule.enabled = not schedule.enabled
        db.commit()
        if schedule.enabled:
            _install_cron(schedule)
        else:
            _remove_cron(schedule)
        return JSONResponse(content={"success": True, "enabled": schedule.enabled})
    finally:
        db.close()


@router.post("/schedules/{schedule_id}/delete")
async def delete_schedule(request: Request, schedule_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        schedule = db.query(BackupSchedule).filter(BackupSchedule.id == schedule_id).first()
        if schedule:
            _remove_cron(schedule)
            db.delete(schedule)
            db.commit()
        return JSONResponse(content={"success": True})
    finally:
        db.close()


@router.post("/vm/{vm_id}/backup")
async def backup_vm_now(request: Request, vm_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse(content={"error": "VM not found"}, status_code=404)

        backup_dir = "/opt/nexve/data/backups"
        import os
        os.makedirs(backup_dir, exist_ok=True)

        disk_path = f"/var/lib/libvirt/images/{vm.name}.qcow2"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{backup_dir}/{vm.name}_{timestamp}.qcow2"

        if os.path.exists(disk_path):
            r = subprocess.run(
                f"cp {disk_path} {backup_path}",
                shell=True, capture_output=True, text=True
            )
            if r.returncode != 0:
                return JSONResponse(content={"success": False, "error": r.stderr})

            # Prune old backups
            _prune_backups(backup_dir, vm.name, 30, 7)

            return JSONResponse(content={"success": True, "path": backup_path})
        else:
            return JSONResponse(content={"success": False, "error": "Disk not found"})
    finally:
        db.close()


@router.post("/container/{ct_id}/backup")
async def backup_container_now(request: Request, ct_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(content=container_service.backup_container(ct_id))


@router.get("/list")
async def list_backups(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    backup_dir = "/opt/nexve/data/backups"
    import os
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)

    backups = []
    for f in sorted(os.listdir(backup_dir)):
        fpath = os.path.join(backup_dir, f)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            backups.append({
                "name": f,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    return JSONResponse(content={"backups": backups})


def _install_cron(schedule):
    cron_line = f"{schedule.cron_expr} /opt/nexve/venv/bin/python3 -c \"import requests; requests.post('http://localhost:8000/api/backups/run-schedule/{schedule.id}')\""
    _remove_cron(schedule)  # Remove first to avoid duplicates
    import os
    crontab_r = subprocess.run("crontab -l 2>/dev/null || true", shell=True, capture_output=True, text=True)
    existing = crontab_r.stdout
    new_crontab = existing.rstrip() + f"\n# NexVE Backup Schedule: {schedule.name}\n{cron_line}\n"
    subprocess.run("crontab -", input=new_crontab, shell=True, capture_output=True, text=True)


def _remove_cron(schedule):
    import re
    crontab_r = subprocess.run("crontab -l 2>/dev/null || true", shell=True, capture_output=True, text=True)
    lines = crontab_r.stdout.splitlines()
    filtered = []
    skip_next = False
    for line in lines:
        if f"NexVE Backup Schedule: {schedule.name}" in line:
            skip_next = True
            continue
        if skip_next and "run-schedule" in line:
            skip_next = False
            continue
        filtered.append(line)
    new_crontab = "\n".join(filtered) + "\n"
    subprocess.run("crontab -", input=new_crontab, shell=True, capture_output=True, text=True)


def _prune_backups(backup_dir, prefix, retention_days, max_backups):
    import os
    import glob
    files = sorted(glob.glob(f"{backup_dir}/{prefix}_*.qcow2"), key=os.path.getmtime, reverse=True)

    # Remove by max count
    for f in files[max_backups:]:
        os.remove(f)

    # Remove by age
    cutoff = datetime.now().timestamp() - (retention_days * 86400)
    for f in files:
        if os.path.getmtime(f) < cutoff:
            os.remove(f)


# ── Backup Restore ──

@router.post("/restore/vm")
async def restore_vm_backup(
    request: Request,
    backup_path: str = Form(...),
    vm_name: str = Form(""),
):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.restore_vm_from_backup(backup_path, vm_name))


@router.post("/restore/container")
async def restore_container_backup(
    request: Request,
    backup_path: str = Form(...),
    ct_id: int = Form(0),
):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.restore_container_from_backup(backup_path, ct_id))


@router.post("/restore/encrypted")
async def restore_encrypted_backup(
    request: Request,
    backup_path: str = Form(...),
    passphrase: str = Form(...),
    vm_name: str = Form(""),
):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.restore_vm_encrypted(backup_path, passphrase, vm_name))


@router.post("/backup/vm/encrypted")
async def backup_vm_encrypted(
    request: Request,
    vm_id: int = Form(...),
    passphrase: str = Form(...),
):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.backup_vm_encrypted(vm_id, passphrase))


@router.post("/backup/vm/incremental")
async def backup_vm_incremental(
    request: Request,
    vm_id: int = Form(...),
):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.backup_vm_incremental(vm_id))


@router.get("/stats")
async def backup_stats(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.get_backup_stats())


@router.get("/pbs/status")
async def pbs_status(request: Request):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.pbs_status())


@router.post("/extract")
async def extract_from_backup(
    request: Request,
    backup_path: str = Form(...),
    file_path: str = Form(...),
    output_path: str = Form("/tmp/nexve-restore"),
):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.extract_file_from_backup(backup_path, file_path, output_path))


@router.delete("/{filename}")
async def delete_backup_file(request: Request, filename: str):
    user = get_current_user(request)
    if not user: return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(backup_svc.delete_backup(filename))

