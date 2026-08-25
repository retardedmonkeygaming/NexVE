from fastapi import APIRouter
import psutil

router = APIRouter()

@router.get("/")
async def list_storage():
    partitions = psutil.disk_partitions()
    storage = []
    for p in partitions:
        try:
            usage = psutil.disk_usage(p.mountpoint)
            storage.append({
                "device": p.device,
                "mountpoint": p.mountpoint,
                "fstype": p.fstype,
                "total": usage.total,
                "used": usage.used,
                "percent": usage.percent
            })
        except PermissionError:
            pass
    return {"storage": storage}
