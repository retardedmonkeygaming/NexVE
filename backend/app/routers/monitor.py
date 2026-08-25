from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.monitor_service import monitor_svc
from ..auth import get_current_user

router = APIRouter()


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
    """Manual trigger for collecting metrics. Also called by background task."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(monitor_svc.collect())
