from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from ..services.iso_service import ISOService
from ..auth import get_current_user
from ..security import generate_csrf_token
import os

router = APIRouter()
iso_svc = ISOService()

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@router.get("/", response_class=HTMLResponse)
async def templates_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
    isos = iso_svc.list_local()
    return templates.TemplateResponse(request=request, name="templates_iso.html", context={
        "user": user, "csrf_token": csrf, "page": "templates",
        "hostname": os.uname().nodename, "isos": isos
    })


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return RedirectResponse(url="/templates", status_code=302)


@router.post("/upload")
async def upload_iso(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    dest = os.path.join(iso_svc.ISO_DIR, file.filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
    return RedirectResponse(url="/templates", status_code=302)


@router.post("/download")
async def download_iso(request: Request, url: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    iso_svc.download(url)
    return RedirectResponse(url="/templates", status_code=302)


@router.get("/delete/{filename}")
async def delete_iso(filename: str, request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    iso_svc.delete(filename)
    return RedirectResponse(url="/templates", status_code=302)
