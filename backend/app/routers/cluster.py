"""
NexVE Cluster Router
API endpoints for cluster management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.cluster_service import ClusterService
from ..auth import get_current_user

router = APIRouter()
cluster_svc = ClusterService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.get("/status")
async def cluster_status(request: Request):
    """Get cluster status."""
    user, redir = auth_check(request)
    if redir:
        return redir
    status = cluster_svc.get_cluster_status()
    return JSONResponse(status)


@router.get("/nodes")
async def list_nodes(request: Request):
    """List cluster nodes."""
    user, redir = auth_check(request)
    if redir:
        return redir
    nodes = cluster_svc.get_nodes()
    return JSONResponse({"nodes": nodes})


@router.post("/create")
async def create_cluster(
    request: Request,
    cluster_name: str = Form("nexve"),
):
    """Create a new cluster on this node."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = cluster_svc.create_cluster(cluster_name)
    return JSONResponse(result)


@router.post("/join")
async def join_cluster(
    request: Request,
    remote_host: str = Form(...),
    cluster_name: str = Form("nexve"),
):
    """Join an existing cluster."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = cluster_svc.join_cluster(remote_host, cluster_name)
    return JSONResponse(result)


@router.delete("/nodes/{node_name}")
async def remove_node(node_name: str, request: Request):
    """Remove a node from the cluster."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = cluster_svc.remove_node(node_name)
    return JSONResponse(result)


@router.post("/destroy")
async def destroy_cluster(request: Request):
    """Destroy the local cluster."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = cluster_svc.destroy_cluster()
    return JSONResponse(result)


@router.post("/tokens/generate")
async def generate_token(
    request: Request,
    node_name: str = Form(...),
):
    """Generate a join token for a new node."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = cluster_svc.generate_join_token(node_name)
    return JSONResponse(result)


@router.post("/tokens/validate")
async def validate_token(
    request: Request,
    token: str = Form(...),
):
    """Validate a join token."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = cluster_svc.validate_join_token(token)
    return JSONResponse(result)


@router.get("/config")
async def get_config(request: Request):
    """Get cluster configuration."""
    user, redir = auth_check(request)
    if redir:
        return redir
    result = cluster_svc.get_cluster_config()
    return JSONResponse(result)
