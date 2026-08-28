from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.monitor_service import MonitorService
from ..auth import get_current_user, api_auth
import psutil

router = APIRouter()
monitor_svc = MonitorService()


@router.get("/current")
async def current_stats(request: Request):
    user, error = api_auth(request)
    if error: return error
    data = monitor_svc.get_current()
    # Ensure all required fields exist with defaults
    return JSONResponse({
        "cpu_percent": data.get("cpu_percent", 0),
        "cpu_count": data.get("cpu_count", 1),
        "cpu_freq_current": data.get("cpu_freq_current", 0),
        "cpu_freq_max": data.get("cpu_freq_max", 0),
        "memory_percent": data.get("memory_percent", 0),
        "memory_used_mb": data.get("memory_used_mb", 0),
        "memory_total_mb": data.get("memory_total_mb", 0),
        "memory_available_mb": data.get("memory_available_mb", 0),
        "disk_percent": data.get("disk_percent", 0),
        "disk_used_gb": data.get("disk_used_gb", 0),
        "disk_total_gb": data.get("disk_total_gb", 0),
        "disk_free_gb": data.get("disk_free_gb", 0),
        "net_sent_bytes": data.get("net_sent_bytes", 0),
        "net_recv_bytes": data.get("net_recv_bytes", 0),
        "net_sent_rate": data.get("net_sent_rate", 0),
        "net_recv_rate": data.get("net_recv_rate", 0),
        "load_1": data.get("load_1", 0),
        "load_5": data.get("load_5", 0),
        "load_15": data.get("load_15", 0),
        "uptime": data.get("uptime", 0),
        "timestamp": data.get("timestamp", ""),
    })


@router.get("/history")
async def history(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(monitor_svc.get_history())


@router.get("/collect")
async def collect(request: Request):
    """Manual trigger for collecting metrics."""
    user, error = api_auth(request)
    if error: return error
    metric = monitor_svc._snapshot()
    monitor_svc._last_snapshot = metric
    monitor_svc._append_metric(metric)
    return JSONResponse(metric)


@router.get("/processes")
async def top_processes(request: Request):
    """Return top processes by CPU usage."""
    user, error = api_auth(request)
    if error: return error
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
        try:
            info = p.info
            procs.append({
                'pid': info['pid'],
                'name': info['name'][:30],
                'cpu': round(info['cpu_percent'] or 0, 1),
                'memory': round(info['memory_percent'] or 0, 1),
                'status': info['status'],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x['cpu'], reverse=True)
    return JSONResponse({'processes': procs[:15]})
