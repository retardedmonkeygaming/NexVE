from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
from collections import defaultdict
import os
from ..database import SessionLocal
from ..models.user import User, Session
from ..security import generate_csrf_token
from ..auth import create_session

router = APIRouter()

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# In-memory rate limiter (resets on restart — fine for homelab)
failed_attempts = defaultdict(list)  # ip -> [timestamp, ...]
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def is_locked_out(ip: str) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=LOCKOUT_MINUTES)
    failed_attempts[ip] = [t for t in failed_attempts[ip] if t > cutoff]
    return len(failed_attempts[ip]) >= MAX_ATTEMPTS


def record_failure(ip: str):
    failed_attempts[ip].append(datetime.utcnow())


def clear_failures(ip: str):
    failed_attempts[ip].clear()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("nexve_session")
    if token:
        db = SessionLocal()
        try:
            s = db.query(Session).filter(Session.token == token).first()
            if s and s.expires_at > datetime.utcnow():
                return RedirectResponse(url="/", status_code=302)
        finally:
            db.close()

    ip = request.client.host
    locked = is_locked_out(ip)
    error = request.query_params.get("error")
    return templates.TemplateResponse(request=request, name="login.html", context={
        "error": "Invalid username or password" if error else None,
        "locked": locked,
    })


@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ip = request.client.host

    if is_locked_out(ip):
        return templates.TemplateResponse(request=request, name="login.html", context={
            "error": "Account locked. Try again in 15 minutes.",
            "locked": True,
        })

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.verify_password(password):
            record_failure(ip)
            return RedirectResponse(url="/login?error=1", status_code=302)

        if not user.is_active:
            return templates.TemplateResponse(request=request, name="login.html", context={
                "error": "Account is disabled.",
                "locked": False,
            })

        clear_failures(ip)

        # Check if 2FA is enabled — redirect to 2FA step
        if user.totp_enabled and user.totp_secret:
            from ..auth import create_session as create_temp_session
            temp_token = create_temp_session(user.id)
            response = RedirectResponse(url="/login/2fa", status_code=302)
            response.set_cookie("nexve_temp_session", temp_token, httponly=True, max_age=300)
            return response

        # No 2FA — create full session
        token = create_session(user.id)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("nexve_session", token, httponly=True, max_age=86400)
        return response
    finally:
        db.close()
