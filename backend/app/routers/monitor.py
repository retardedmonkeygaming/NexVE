from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.monitor_service import MonitorService
from ..auth import get_current_user
import psutil

router = APIRouter()
monitor_svc = MonitorService()


@router.get("/current")
async def current_stats(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(monitor_svc.get_current())


@router.get("/history")
async def history(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(monitor_svc.get_history())


@router.get("/collect")
async def collect(request: Request):
    """Manual trigger for collecting metrics."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    metric = monitor_svc._snapshot()
    monitor_svc._append_metric(metric)
    return JSONResponse(metric)


@router.get("/processes")
async def top_processes(request: Request):
    """Return top processes by CPU usage."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
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
