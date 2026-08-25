from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timedelta
from collections import defaultdict
from ..database import SessionLocal
from ..models.user import User, Session
from ..security import generate_csrf_token
from ..auth import create_session
import bcrypt

router = APIRouter()

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
    csrf = generate_csrf_token("login")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE — Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0a0a0a] text-white min-h-screen flex items-center justify-center">
    <div class="bg-[#111] border border-[#222] rounded-xl p-8 w-full max-w-md">
        <h1 class="text-2xl font-bold mb-2 text-center">NexVE</h1>
        <p class="text-gray-500 text-center mb-6 text-sm">Hypervisor Management</p>
        {"<p class='text-red-500 text-center mb-4 text-sm'>Account locked. Try again in 15 minutes.</p>" if locked else ""}
        <form method="POST" action="/login" class="space-y-4">
            <input type="hidden" name="csrf_token" value="{csrf}">
            <div>
                <label class="text-gray-400 text-sm">Username</label>
                <input name="username" type="text" required
                    class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-3 mt-1 focus:border-orange-500 focus:outline-none"
                    {"disabled" if locked else ""}>
            </div>
            <div>
                <label class="text-gray-400 text-sm">Password</label>
                <input name="password" type="password" required
                    class="w-full bg-[#1a1a1a] border border-[#333] rounded-lg px-4 py-3 mt-1 focus:border-orange-500 focus:outline-none"
                    {"disabled" if locked else ""}>
            </div>
            <button type="submit" {"disabled" if locked else ""}
                class="w-full bg-orange-600 hover:bg-orange-700 text-white py-3 rounded-lg font-semibold transition">
                Sign In
            </button>
        </form>
    </div>
</body>
</html>"""

@router.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    ip = request.client.host

    from ..security import validate_csrf_token
    if not validate_csrf_token(csrf_token, "login"):
        return HTMLResponse("Invalid form", status_code=400)

    if is_locked_out(ip):
        return HTMLResponse("Account locked. Try again later.", status_code=429)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.verify_password(password):
            record_failure(ip)
            return RedirectResponse(url="/login?error=1", status_code=302)

        if not user.is_active:
            return HTMLResponse("Account disabled", status_code=403)

        clear_failures(ip)
        token = create_session(user.id)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("nexve_session", token, httponly=True, max_age=86400)
        return response
    finally:
        db.close()
