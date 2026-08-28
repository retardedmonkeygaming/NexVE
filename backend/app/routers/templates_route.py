"""
NexVE ISO Templates Router v3.0
Handles ISO upload, download, listing, and serving.
"""
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from ..services.iso_service import ISOService
from ..auth import get_current_user, api_auth
from ..security import generate_csrf_token
import os

router = APIRouter()
iso_svc = ISOService()

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@router.get("/", response_class=HTMLResponse)
async def templates_page(request: Request):
    user, error = api_auth(request)
    if error: return error
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    isos = iso_svc.list_local()
    return templates.TemplateResponse(request=request, name="templates_iso.html", context={
        "user": user, "csrf_token": csrf, "page": "templates",
        "hostname": os.uname().nodename, "isos": isos,
    })


@router.get("/api/list")
async def api_list_isos(request: Request):
    """List ISOs as JSON for AJAX calls."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"isos": []})
    isos = iso_svc.list_local()
    return JSONResponse({"isos": isos})


@router.post("/upload")
async def upload_iso(request: Request, file: UploadFile = File(...)):
    user, error = api_auth(request)
    if error: return error

    dest = os.path.join(iso_svc.ISO_DIR, file.filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    # Always return JSON for AJAX (XHR) or redirect for form POST
    xreq = request.headers.get("x-requested-with", "")
    if "xmlhttprequest" in xreq.lower():
        return JSONResponse({"success": True, "filename": file.filename})
    return RedirectResponse(url="/templates", status_code=303)


@router.post("/api/upload")
async def api_upload_iso(request: Request, file: UploadFile = File(...)):
    """API endpoint for ISO upload (returns JSON)."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    dest = os.path.join(iso_svc.ISO_DIR, file.filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    return JSONResponse({"success": True, "filename": file.filename})


@router.post("/download")
async def download_iso(request: Request, url: str = Form(...), name: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    result = iso_svc.download(url, name)
    if result.get("success"):
        return RedirectResponse(url="/templates", status_code=303)
    return JSONResponse(result)


@router.get("/delete/{filename:path}")
async def delete_iso(filename: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    iso_svc.delete(filename)
    # Return JSON for AJAX, redirect for browser
    xreq = request.headers.get("x-requested-with", "")
    if "xmlhttprequest" in xreq.lower():
        return JSONResponse({"success": True, "filename": filename})
    return RedirectResponse(url="/templates", status_code=303)


@router.get("/serve/{filename:path}")
async def serve_iso(filename: str, request: Request):
    """Serve an ISO file for download."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    filepath = iso_svc.get_path(filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, filename=filename, media_type="application/octet-stream")
    return JSONResponse({"error": "File not found"}, status_code=404)
