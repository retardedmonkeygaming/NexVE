"""
NexVE Ceph Router
API endpoints for Ceph distributed storage management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.ceph_service import CephService
from ..auth import get_current_user, api_auth

router = APIRouter()
ceph_svc = CephService()



@router.get("/status")
async def ceph_status(request: Request):
    """Get Ceph cluster status."""
    user, error = api_auth(request)
    if error: return error
    status = ceph_svc.get_ceph_status()
    return JSONResponse(status)


@router.get("/osds")
async def list_osds(request: Request):
    """List OSDs."""
    user, error = api_auth(request)
    if error: return error
    osds = ceph_svc.get_osd_list()
    return JSONResponse({"osds": osds})


@router.get("/pools")
async def list_pools(request: Request):
    """List RBD pools."""
    user, error = api_auth(request)
    if error: return error
    pools = ceph_svc.list_pools()
    return JSONResponse({"pools": pools})


@router.post("/pools")
async def create_pool(
    request: Request,
    name: str = Form(...),
    pg_num: int = Form(128),
):
    """Create an RBD pool."""
    user, error = api_auth(request)
    if error: return error
    result = ceph_svc.create_pool(name, pg_num)
    return JSONResponse(result)


@router.delete("/pools/{name}")
async def delete_pool(name: str, request: Request):
    """Delete an RBD pool."""
    user, error = api_auth(request)
    if error: return error
    result = ceph_svc.delete_pool(name)
    return JSONResponse(result)


@router.get("/images")
async def list_images(request: Request, pool: str = "rbd"):
    """List RBD images."""
    user, error = api_auth(request)
    if error: return error
    images = ceph_svc.list_images(pool)
    return JSONResponse({"images": images})


@router.post("/images")
async def create_image(
    request: Request,
    pool: str = Form("rbd"),
    name: str = Form(...),
    size_gb: int = Form(10),
):
    """Create an RBD image."""
    user, error = api_auth(request)
    if error: return error
    result = ceph_svc.create_image(pool, name, size_gb)
    return JSONResponse(result)


@router.delete("/images/{pool}/{name}")
async def delete_image(pool: str, name: str, request: Request):
    """Delete an RBD image."""
    user, error = api_auth(request)
    if error: return error
    result = ceph_svc.delete_image(pool, name)
    return JSONResponse(result)


@router.post("/images/resize")
async def resize_image(
    request: Request,
    pool: str = Form("rbd"),
    name: str = Form(...),
    size_gb: int = Form(...),
):
    """Resize an RBD image."""
    user, error = api_auth(request)
    if error: return error
    result = ceph_svc.resize_image(pool, name, size_gb)
    return JSONResponse(result)


@router.get("/cephfs")
async def list_cephfs(request: Request):
    """List CephFS filesystems."""
    user, error = api_auth(request)
    if error: return error
    fs = ceph_svc.list_cephfs()
    return JSONResponse({"filesystems": fs})

@router.post("/osd/{action}")
async def osd_action(request: Request, action: str, osd_id: str = Form(...)):
    """Perform an action on a Ceph OSD (in, out, up, down, reweight)."""
    user, error = api_auth(request)
    if error: return error
    import subprocess
    if action in ("in", "out", "up", "down"):
        r = subprocess.run(["ceph", "osd", action, osd_id], capture_output=True, text=True, timeout=30)
        return JSONResponse({"success": r.returncode == 0, "output": r.stdout.strip(), "error": r.stderr.strip() if r.returncode != 0 else None})
    elif action == "reweight":
        form = await request.form()
        weight = form.get("weight", "1.0")
        r = subprocess.run(["ceph", "osd", "reweight", osd_id, str(weight)], capture_output=True, text=True, timeout=30)
        return JSONResponse({"success": r.returncode == 0, "output": r.stdout.strip(), "error": r.stderr.strip() if r.returncode != 0 else None})
    return JSONResponse({"success": False, "error": f"Unknown action: {action}"})
