from fastapi import APIRouter
import psutil
import platform

router = APIRouter()

@router.get("/")
async def list_nodes():
    return {
        "nodes": [{
            "name": platform.node(),
            "status": "online",
            "cpu": psutil.cpu_percent(),
            "memory": psutil.virtual_memory()._asdict(),
            "uptime": psutil.boot_time()
        }]
    }

@router.get("/{node_name}")
async def get_node(node_name: str):
    return {
        "name": platform.node(),
        "status": "online",
        "cpu": {
            "percent": psutil.cpu_percent(),
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        },
        "memory": psutil.virtual_memory()._asdict(),
        "disk": psutil.disk_usage('/')._asdict(),
        "platform": platform.platform()
    }
