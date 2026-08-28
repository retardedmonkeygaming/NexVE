"""
NexVE Cluster Management Router
API endpoints for cluster node management, status, and cross-node operations.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.cluster_service import ClusterService
from ..services.proxy_service import ProxyService
from ..services.migration_service import MigrationService
from ..auth import get_current_user, api_auth

router = APIRouter()
cluster_svc = ClusterService()
proxy_svc = ProxyService()
migration_svc = MigrationService()



@router.get("/status")
async def cluster_overview(request: Request):
    """Get comprehensive cluster status including all node health."""
    user, error = api_auth(request)
    if error: return error

    cluster_status = cluster_svc.get_cluster_status()
    nodes_status = await proxy_svc.get_all_nodes_status()

    return JSONResponse({
        "clustered": cluster_status.get("clustered", False),
        "quorum": cluster_status.get("quorum", {}),
        "nodes": nodes_status,
        "local_node": proxy_svc.get_local_hostname(),
    })


@router.get("/nodes")
async def list_nodes(request: Request):
    """List all cluster nodes with live status."""
    user, error = api_auth(request)
    if error: return error

    nodes = cluster_svc.get_nodes()
    nodes_status = await proxy_svc.get_all_nodes_status()

    # Merge cluster info with live status
    for node in nodes:
        for status in nodes_status:
            if status["name"] == node["name"]:
                node.update(status)
                break

    return JSONResponse({"nodes": nodes})


@router.post("/nodes/{node_name}/migrate-vm")
async def migrate_vm_to_node(
    request: Request,
    node_name: str,
    vm_id: int = Form(...),
    live: bool = Form(True),
):
    """Migrate a VM to another cluster node."""
    user, error = api_auth(request)
    if error: return error

    from ..database import SessionLocal
    from ..models.vm import VM

    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)

        if proxy_svc.is_local(node_name):
            return JSONResponse({"error": "Cannot migrate to same node"})

        result = migration_svc.migrate_vm(vm.name, node_name, live)
        return JSONResponse(result)
    finally:
        db.close()


@router.post("/nodes/{node_name}/migrate-container")
async def migrate_container_to_node(
    request: Request,
    node_name: str,
    ct_id: int = Form(...),
):
    """Migrate a container to another cluster node."""
    user, error = api_auth(request)
    if error: return error

    if proxy_svc.is_local(node_name):
        return JSONResponse({"error": "Cannot migrate to same node"})

    result = migration_svc.migrate_container(ct_id, node_name)
    return JSONResponse(result)


@router.post("/forward/{target_node}/{path:path}")
async def forward_to_node(
    request: Request,
    target_node: str,
    path: str,
):
    """Forward an arbitrary API request to another node."""
    user, error = api_auth(request)
    if error: return error

    body = None
    if request.method in ("POST", "PUT"):
        try:
            body = await request.json()
        except Exception:
            pass

    result = await proxy_svc.forward_request(
        request.method, target_node, f"/api/{path}", body=body
    )
    return JSONResponse(result)


@router.get("/resources")
async def cluster_resources(request: Request):
    """Get resource distribution across all nodes."""
    user, error = api_auth(request)
    if error: return error

    nodes_status = await proxy_svc.get_all_nodes_status()
    total_cpu = sum(n.get("cpu_percent", 0) for n in nodes_status)
    total_mem = sum(n.get("memory_percent", 0) for n in nodes_status)
    node_count = len(nodes_status) or 1

    return JSONResponse({
        "nodes": nodes_status,
        "summary": {
            "total_nodes": len(nodes_status),
            "online_nodes": sum(1 for n in nodes_status if n.get("status") == "online"),
            "avg_cpu": round(total_cpu / node_count, 1),
            "avg_memory": round(total_mem / node_count, 1),
        }
    })
