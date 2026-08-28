from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from datetime import datetime
from ..services.storage_service import StorageService
from ..auth import get_current_user, api_auth
from ..database import SessionLocal
from ..models.storage import Storage
import os

router = APIRouter()
svc = StorageService()



# ── Overview ──

@router.get("/overview")
async def storage_overview(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.get_storage_overview())


# ── Disks ──

@router.get("/disks")
async def list_disks(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"disks": svc.list_disks()})


@router.get("/disks/{device}/health")
async def disk_health(request: Request, device: str):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.disk_health(device))


@router.post("/disk/wipe")
async def wipe_disk(request: Request, device: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    if not device.startswith("/dev/sd") and not device.startswith("/dev/vd"):
        return JSONResponse(content={"success": False, "error": "Invalid device path"})
    return JSONResponse(content=svc.wipe_disk(device))


@router.post("/disk/move")
async def move_disk(
    request: Request,
    vm_name: str = Form(...),
    source_storage: str = Form(...),
    target_storage: str = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(content=svc.move_disk(vm_name, source_storage, target_storage))


# ── Content Browser ──

@router.get("/content/{storage_name}")
async def browse_storage_content(request: Request, storage_name: str):
    user, error = api_auth(request)
    if error: return error

    paths = {
        "local": "/var/lib/vz",
        "backups": "/opt/nexve/data/backups",
        "isos": "/opt/nexve/data/isos",
    }
    base = paths.get(storage_name, "/var/lib/vz")

    items = []
    if os.path.exists(base):
        for f in sorted(os.listdir(base)):
            fpath = os.path.join(base, f)
            stat = os.stat(fpath)
            items.append({
                "name": f,
                "is_dir": os.path.isdir(fpath),
                "size_bytes": stat.st_size if os.path.isfile(fpath) else 0,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    return JSONResponse(content={"path": base, "items": items})


# ── ZFS ──

@router.get("/zfs/pools")
async def zfs_pools(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"pools": svc.zfs_list_pools()})



@router.get("/zfs/status")
async def zfs_check_status(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.zfs_status())

@router.post("/zfs/pools")
async def zfs_create_pool(request: Request, name: str = Form(...), device: str = Form(""),
                          force: bool = Form(False), pool_type: str = Form("single"),
                          devices: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    dev_list = [d.strip() for d in devices.split(",") if d.strip()] if devices else None
    result = svc.zfs_create_pool(name, device, force, pool_type=pool_type, devices=dev_list)
    return JSONResponse(result)


@router.delete("/zfs/pools/{name}")
async def zfs_delete_pool(request: Request, name: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.zfs_destroy_pool(name)
    return JSONResponse(result)


@router.get("/zfs/volumes")
async def zfs_volumes(request: Request, pool: str = ""):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"volumes": svc.zfs_list_volumes(pool)})


@router.post("/zfs/volumes")
async def zfs_create_volume(request: Request, pool: str = Form(...), name: str = Form(...), size_gb: int = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.zfs_create_volume(pool, name, size_gb)
    return JSONResponse(result)


@router.post("/zfs/snapshot")
async def zfs_snap(request: Request, volume: str = Form(...), snap_name: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.zfs_snapshot(volume, snap_name)
    return JSONResponse(result)


@router.get("/zfs/snapshots/{volume}")
async def zfs_snapshots(request: Request, volume: str):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"snapshots": svc.zfs_snapshots(volume)})


@router.post("/zfs/scrub/{pool}")
async def zfs_scrub(request: Request, pool: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.zfs_scrub(pool)
    return JSONResponse(result)


@router.delete("/zfs/volumes/{volume:path}")
async def zfs_delete_volume(request: Request, volume: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.zfs_destroy(volume)
    return JSONResponse(result)


# ── ZFS Replication ──

@router.post("/zfs/replicate")
async def zfs_replicate(
    request: Request,
    source: str = Form(...),
    target: str = Form(...),
    snapshot: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error
    result = svc.zfs_replicate(source, target, snapshot)
    return JSONResponse(result)


@router.get("/zfs/replication/status")
async def zfs_replication_status(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"jobs": svc.zfs_replication_status()})


# ── LVM ──

@router.get("/lvm/vgs")
async def lvm_vgs(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"vgs": svc.lvm_list_vgs()})


@router.get("/lvm/lvs")
async def lvm_lvs(request: Request, vg: str = ""):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"lvs": svc.lvm_list_lvs(vg)})


@router.post("/lvm/vgs")
async def lvm_create_vg(request: Request, name: str = Form(...), device: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.lvm_create_vg(name, device)
    return JSONResponse(result)


@router.post("/lvm/lvs")
async def lvm_create_lv(request: Request, vg_name: str = Form(...), lv_name: str = Form(...), size_gb: int = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.lvm_create_lv(vg_name, lv_name, size_gb)
    return JSONResponse(result)


@router.delete("/lvm/vgs/{name}")
async def lvm_delete_vg(request: Request, name: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.lvm_remove_vg(name)
    return JSONResponse(result)


@router.delete("/lvm/lvs/{lv_path:path}")
async def lvm_delete_lv(request: Request, lv_path: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.lvm_remove_lv(lv_path)
    return JSONResponse(result)


@router.post("/lvm/lvs/resize")
async def lvm_resize_lv(
    request: Request,
    lv_path: str = Form(...),
    size_gb: int = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    result = svc.lvm_resize_lv(lv_path, size_gb)
    return JSONResponse(result)


# ── Directory ──

@router.get("/dir")
async def dir_usage(request: Request, path: str = "/var/lib/vz"):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.dir_usage(path))


# ── NFS ──

@router.get("/nfs")
async def nfs_mounts(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"mounts": svc.nfs_list_mounts()})


@router.post("/nfs/mount")
async def nfs_mount(request: Request, host: str = Form(...), path: str = Form(...), mountpoint: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.nfs_mount(host, path, mountpoint)
    return JSONResponse(result)


@router.post("/nfs/unmount")
async def nfs_unmount(request: Request, mountpoint: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.nfs_unmount(mountpoint)
    return JSONResponse(result)


# ── CIFS/SMB ──

@router.post("/cifs/mount")
async def cifs_mount(
    request: Request,
    host: str = Form(...),
    share: str = Form(...),
    mountpoint: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error
    result = svc.cifs_mount(host, share, mountpoint, username, password)
    return JSONResponse(result)


@router.post("/cifs/unmount")
async def cifs_unmount(request: Request, mountpoint: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.cifs_unmount(mountpoint)
    return JSONResponse(result)


# ── iSCSI ──

@router.post("/iscsi/discover")
async def iscsi_discover(request: Request, target: str = Form(...), port: int = Form(3260)):
    user, error = api_auth(request)
    if error: return error
    result = svc.iscsi_discover(target, port)
    return JSONResponse({"targets": result})


@router.post("/iscsi/login")
async def iscsi_login(
    request: Request,
    target: str = Form(...),
    portal: str = Form(...),
    port: int = Form(3260),
):
    user, error = api_auth(request)
    if error: return error
    result = svc.iscsi_login(target, portal, port)
    return JSONResponse(result)


@router.post("/iscsi/logout")
async def iscsi_logout(request: Request, target: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.iscsi_logout(target)
    return JSONResponse(result)


@router.get("/iscsi/sessions")
async def iscsi_sessions(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"sessions": svc.iscsi_list_sessions()})


# ── BTRFS ──

@router.get("/btrfs/pools")
async def btrfs_pools(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"pools": svc.btrfs_list_pools()})


@router.get("/btrfs/subvolumes/{pool}")
async def btrfs_subvolumes(request: Request, pool: str):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"subvolumes": svc.btrfs_list_subvolumes(pool)})


@router.post("/btrfs/subvolume")
async def btrfs_create_subvolume(request: Request, pool: str = Form(...), name: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.btrfs_create_subvolume(pool, name)
    return JSONResponse(result)


@router.delete("/btrfs/subvolume/{path:path}")
async def btrfs_delete_subvolume(request: Request, path: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.btrfs_delete_subvolume(path)
    return JSONResponse(result)


@router.post("/btrfs/snapshot")
async def btrfs_snapshot(request: Request, source: str = Form(...), dest: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.btrfs_snapshot(source, dest)
    return JSONResponse(result)


# ── Storage Quotas ──

@router.get("/quotas")
async def list_quotas(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"quotas": svc.list_quotas()})


@router.post("/quotas")
async def set_quota(
    request: Request,
    path: str = Form(...),
    size_gb: int = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    result = svc.set_quota(path, size_gb)
    return JSONResponse(result)


# ── Storage Migration ──

@router.post("/migrate")
async def migrate_disk(
    request: Request,
    vm_name: str = Form(...),
    disk_index: int = Form(0),
    target_storage: str = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    result = svc.migrate_disk(vm_name, disk_index, target_storage)
    return JSONResponse(result)


# ── ISOs ──

@router.get("/isos")
async def list_isos(request: Request):
    user, error = api_auth(request)
    if error: return error
    from ..services.iso_service import ISOService
    iso_svc = ISOService()
    return JSONResponse({"isos": iso_svc.list_local()})


# ── Registered storage backends ──

@router.get("/backends")

# ── LVM-thin endpoints ──

@router.get("/lvm-thin/pools")
async def lvm_thin_pools(request: Request, vg: str = ""):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_list_pools(vg))


@router.post("/lvm-thin/pools/create")
async def lvm_thin_create_pool(
    request: Request,
    vg_name: str = Form(...),
    pool_name: str = Form(...),
    size_gb: int = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_create_pool(vg_name, pool_name, size_gb))


@router.delete("/lvm-thin/pools/{vg_name}/{pool_name}")
async def lvm_thin_delete_pool(request: Request, vg_name: str, pool_name: str):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_remove_pool(vg_name, pool_name))


@router.get("/lvm-thin/volumes")
async def lvm_thin_volumes(request: Request, vg: str = "", pool: str = ""):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_list_volumes(vg, pool))


@router.post("/lvm-thin/volumes/create")
async def lvm_thin_create_volume(
    request: Request,
    vg_name: str = Form(...),
    pool_name: str = Form(...),
    lv_name: str = Form(...),
    size_gb: int = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_create_lv(vg_name, pool_name, lv_name, size_gb))


@router.delete("/lvm-thin/volumes/{lv_path:path}")
async def lvm_thin_delete_volume(request: Request, lv_path: str):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_remove_lv(lv_path))


@router.post("/lvm-thin/snapshot")
async def lvm_thin_snapshot_create(
    request: Request,
    source_lv: str = Form(...),
    snap_name: str = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_snapshot(source_lv, snap_name))


@router.get("/lvm-thin/snapshots")
async def lvm_thin_snapshots(request: Request, vg: str = ""):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.lvm_thin_list_snapshots(vg))


@router.post("/migrate")
async def storage_migrate(
    request: Request,
    source: str = Form(...),
    target: str = Form(...),
):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.migrate_storage(source, target))


async def list_backends(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        backends = db.query(Storage).all()
        return JSONResponse({
            "backends": [
                {
                    "id": b.id,
                    "name": b.name,
                    "type": b.type,
                    "path": b.path,
                    "pool_name": b.pool_name,
                    "vg_name": b.vg_name,
                    "enabled": b.enabled,
                    "total_gb": b.total_gb,
                    "used_gb": b.used_gb,
                }
                for b in backends
            ]
        })
    finally:
        db.close()


@router.post("/backends")
async def add_backend(
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    path: str = Form(""),
    pool_name: str = Form(""),
    vg_name: str = Form(""),
    remote_host: str = Form(""),
    remote_path: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        backend = Storage(
            name=name, type=type, path=path, pool_name=pool_name,
            vg_name=vg_name, remote_host=remote_host, remote_path=remote_path,
        )
        db.add(backend)
        db.commit()
        return JSONResponse({"success": True, "id": backend.id})
    finally:
        db.close()


@router.delete("/backends/{backend_id}")
async def remove_backend(request: Request, backend_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        db.query(Storage).filter(Storage.id == backend_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


# ── GlusterFS endpoints ──

@router.get("/gluster/status")
async def gluster_status(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.gluster_status())


@router.get("/gluster/volumes")
async def gluster_volumes(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"volumes": svc.gluster_list_volumes()})


@router.post("/gluster/volume")
async def gluster_create_volume(request: Request, name: str = Form(...), bricks: str = Form(...),
                               replica: int = Form(1)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.gluster_create_volume(name, bricks.split(), replica))


@router.delete("/gluster/volume/{name}")
async def gluster_delete_volume(name: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.gluster_delete_volume(name))


@router.post("/gluster/peer/probe")
async def gluster_peer_probe(request: Request, host: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.gluster_peer_probe(host))


@router.post("/gluster/peer/detach")
async def gluster_peer_detach(request: Request, host: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.gluster_peer_detach(host))


# ── RAIDZ Expansion endpoints ──

@router.post("/zfs/raidz/expand")
async def zfs_raidz_expand(request: Request, pool: str = Form(...), device: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.zfs_raidz_expand(pool, device))


@router.get("/zfs/raidz/status/{pool}")
async def zfs_raidz_status(pool: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.zfs_raidz_status(pool))


@router.post("/zfs/raidz/add-vdev")
async def zfs_raidz_add_vdev(request: Request, pool: str = Form(...), devices: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.zfs_raidz_add_vdev(pool, devices.split()))


# ── Replication Job endpoints ──

@router.get("/replication/jobs")
async def replication_jobs(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"jobs": svc.replication_list_jobs()})


@router.post("/replication/job")
async def replication_create_job(request: Request, source: str = Form(...), target: str = Form(...),
                               schedule: str = Form("daily"), recursive: bool = Form(True)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.replication_create_job(source, target, schedule, recursive))


@router.delete("/replication/job/{job_id}")
async def replication_delete_job(job_id: int, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.replication_delete_job(job_id))


@router.post("/replication/job/{job_id}/run")
async def replication_run_now(job_id: int, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.replication_run_now(job_id))
