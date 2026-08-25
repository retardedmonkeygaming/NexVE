from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from ..database import SessionLocal
from ..models.user import User
from ..auth import get_current_user, generate_totp_secret, get_totp_uri, verify_totp, create_session
from ..security import generate_csrf_token
import pyotp
import qrcode
import io
import base64

router = APIRouter()


@router.get("/settings/2fa", response_class=HTMLResponse)
async def two_factor_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        totp_enabled = db_user.totp_enabled if db_user else False
    finally:
        db.close()

    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))

    from fastapi.templating import Jinja2Templates
    import os
    templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../templates"))
    return templates.TemplateResponse(request=request, name="2fa_setup.html", context={
        "user": user, "csrf_token": csrf, "totp_enabled": totp_enabled,
        "qr_code": None, "secret": None
    })


@router.post("/settings/2fa/enable")
async def enable_2fa(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    secret = generate_totp_secret()

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        db_user.totp_secret = secret
        db_user.totp_enabled = False  # Will be enabled after verification
        db.commit()
    finally:
        db.close()

    # Generate QR code
    uri = get_totp_uri(secret, user["username"])
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))

    from fastapi.templating import Jinja2Templates
    import os
    templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../templates"))
    return templates.TemplateResponse(request=request, name="2fa_setup.html", context={
        "user": user, "csrf_token": csrf, "totp_enabled": False,
        "qr_code": f"data:image/png;base64,{qr_b64}", "secret": secret
    })


@router.post("/settings/2fa/verify")
async def verify_2fa_setup(
    request: Request,
    totp_code: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        if not db_user or not db_user.totp_secret:
            return RedirectResponse(url="/settings/2fa", status_code=302)

        if verify_totp(db_user.totp_secret, totp_code):
            db_user.totp_enabled = True
            db.commit()
            # Success — redirect back
            from fastapi.templating import Jinja2Templates
            import os
            templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../templates"))
            csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
            return templates.TemplateResponse(request=request, name="2fa_setup.html", context={
                "user": user, "csrf_token": csrf, "totp_enabled": True,
                "qr_code": None, "secret": None, "success": "2FA enabled successfully!"
            })
        else:
            # Wrong code — show QR again with error
            uri = get_totp_uri(db_user.totp_secret, user["username"])
            qr = qrcode.QRCode(version=1, box_size=8, border=2)
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            csrf = generate_csrf_token(request.cookies.get("nexve_session", ""))
            from fastapi.templating import Jinja2Templates
            import os
            templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../templates"))
            return templates.TemplateResponse(request=request, name="2fa_setup.html", context={
                "user": user, "csrf_token": csrf, "totp_enabled": False,
                "qr_code": f"data:image/png;base64,{qr_b64}",
                "secret": db_user.totp_secret, "error": "Invalid code. Try again."
            })
    finally:
        db.close()


@router.post("/settings/2fa/disable")
async def disable_2fa(request: Request, csrf_token: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from ..security import validate_csrf_token
    session_token = request.cookies.get("nexve_session", "")
    if not validate_csrf_token(csrf_token, session_token):
        return HTMLResponse("CSRF failed", status_code=403)

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        db_user.totp_enabled = False
        db_user.totp_secret = None
        db.commit()
    finally:
        db.close()

    return RedirectResponse(url="/settings/2fa", status_code=302)
