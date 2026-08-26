from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from ..database import SessionLocal
from ..models.user import User

router = APIRouter()

SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexVE — Initial Setup</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>body { background: #0a0a0a; color: #e5e5e5; font-family: system-ui, sans-serif; }</style>
</head>
<body class="min-h-screen flex items-center justify-center">
    <div class="w-full max-w-md">
        <div class="text-center mb-8">
            <h1 class="text-4xl font-bold"><span class="text-orange-500">Nex</span>VE</h1>
            <p class="text-gray-500 mt-2">Initial System Setup</p>
        </div>
        <div class="bg-[#111] border border-gray-800 rounded-xl p-8">
            <h2 class="text-xl font-semibold mb-1">Create Admin Account</h2>
            <p class="text-gray-500 text-sm mb-6">This will be the administrator for your NexVE system.</p>
            <form hx-post="/setup/complete" hx-swap="innerHTML" class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Username</label>
                    <input type="text" name="username" required
                        class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-4 py-3 text-white focus:border-orange-500 focus:outline-none transition"
                        placeholder="admin">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Email</label>
                    <input type="email" name="email" required
                        class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-4 py-3 text-white focus:border-orange-500 focus:outline-none transition"
                        placeholder="you@example.com">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Password</label>
                    <input type="password" name="password" required minlength="8"
                        class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-4 py-3 text-white focus:border-orange-500 focus:outline-none transition"
                        placeholder="Min 8 characters">
                </div>
                <div>
                    <label class="block text-sm text-gray-400 mb-1">Confirm Password</label>
                    <input type="password" name="password_confirm" required minlength="8"
                        class="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-4 py-3 text-white focus:border-orange-500 focus:outline-none transition"
                        placeholder="Repeat password">
                </div>
                <div id="setup-error"></div>
                <button type="submit"
                    class="w-full bg-orange-500 hover:bg-orange-600 text-white font-semibold py-3 rounded-lg transition mt-2">
                    Complete Setup &rarr;
                </button>
            </form>
        </div>
        <p class="text-center text-gray-600 text-xs mt-6">NexVE v1.0 &mdash; Your private hypervisor</p>
    </div>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def setup_page(request: Request):
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return RedirectResponse(url="/", status_code=302)
    finally:
        db.close()
    return SETUP_HTML


@router.post("/complete")
async def complete_setup(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    if password != password_confirm:
        return HTMLResponse(
            '<div class="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-2 rounded-lg mb-4">Passwords do not match.</div>'
        )

    if len(password) < 8:
        return HTMLResponse(
            '<div class="bg-red-500/10 border border-red-500/30 text-red-400 text-sm px-4 py-2 rounded-lg mb-4">Password must be at least 8 characters.</div>'
        )

    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return RedirectResponse(url="/", status_code=302)

        user = User(username=username, email=email, role="admin")
        user.set_password(password)
        db.add(user)
        db.commit()
    finally:
        db.close()

    return HTMLResponse(
        '<div class="bg-green-500/10 border border-green-500/30 text-green-400 text-sm px-4 py-2 rounded-lg mb-4">Account created! Redirecting...</div>'
        '<script>setTimeout(function(){ window.location.href = "/login"; }, 1000);</script>'
    )
