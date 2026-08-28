"""
NexVE Cluster Router
API endpoints for cluster management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.cluster_service import ClusterService
from ..auth import get_current_user, api_auth

router = APIRouter()
cluster_svc = ClusterService()



@router.get("/status")
async def cluster_status(request: Request):
    """Get cluster status."""
    user, error = api_auth(request)
    if error: return error
    status = cluster_svc.get_cluster_status()
    return JSONResponse(status)


@router.get("/nodes")
async def list_nodes(request: Request):
    """List cluster nodes."""
    user, error = api_auth(request)
    if error: return error
    nodes = cluster_svc.get_nodes()
    return JSONResponse({"nodes": nodes})


@router.post("/create")
async def create_cluster(
    request: Request,
    cluster_name: str = Form("nexve"),
):
    """Create a new cluster on this node."""
    user, error = api_auth(request)
    if error: return error
    result = cluster_svc.create_cluster(cluster_name)
    return JSONResponse(result)


@router.post("/join")
async def join_cluster(
    request: Request,
    remote_host: str = Form(...),
    cluster_name: str = Form("nexve"),
):
    """Join an existing cluster."""
    user, error = api_auth(request)
    if error: return error
    result = cluster_svc.join_cluster(remote_host, cluster_name)
    return JSONResponse(result)


@router.delete("/nodes/{node_name}")
async def remove_node(node_name: str, request: Request):
    """Remove a node from the cluster."""
    user, error = api_auth(request)
    if error: return error
    result = cluster_svc.remove_node(node_name)
    return JSONResponse(result)


@router.post("/destroy")
async def destroy_cluster(request: Request):
    """Destroy the local cluster."""
    user, error = api_auth(request)
    if error: return error
    result = cluster_svc.destroy_cluster()
    return JSONResponse(result)


@router.post("/tokens/generate")
async def generate_token(
    request: Request,
    node_name: str = Form(...),
):
    """Generate a join token for a new node."""
    user, error = api_auth(request)
    if error: return error
    result = cluster_svc.generate_join_token(node_name)
    return JSONResponse(result)


@router.post("/tokens/validate")
async def validate_token(
    request: Request,
    token: str = Form(...),
):
    """Validate a join token."""
    user, error = api_auth(request)
    if error: return error
    result = cluster_svc.validate_join_token(token)
    return JSONResponse(result)


@router.get("/config")
async def get_config(request: Request):
    """Get cluster configuration."""
    user, error = api_auth(request)
    if error: return error
    result = cluster_svc.get_cluster_config()
    return JSONResponse(result)


# ── pmxcfs endpoints ──

@router.get("/pmxcfs/status")
async def pmxcfs_status(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.pmxcfs_status())


@router.get("/pmxcfs/read")
async def pmxcfs_read(request: Request, path: str = ""):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.pmxcfs_read(path))


@router.post("/pmxcfs/write")
async def pmxcfs_write(request: Request, path: str = Form(...), content: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.pmxcfs_write(path, content))


@router.get("/pmxcfs/list")
async def pmxcfs_list(request: Request, path: str = ""):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.pmxcfs_list(path))


@router.delete("/pmxcfs/{path:path}")
async def pmxcfs_delete(path: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.pmxcfs_delete(path))


# ── Watchdog fencing endpoints ──

@router.get("/watchdog/status")
async def watchdog_status(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.watchdog_status())


@router.post("/watchdog/enable")
async def watchdog_enable(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.watchdog_enable())


@router.post("/watchdog/disable")
async def watchdog_disable(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.watchdog_disable())


# ── Multi-master endpoints ──

@router.get("/multi-master/status")
async def multi_master_status(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.get_multi_master_status())


@router.get("/node-resources/{node_name}")
async def node_resources(node_name: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(cluster_svc.get_node_resources(node_name))
