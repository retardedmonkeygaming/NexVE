from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.user import User
from ..services.totp_service import TOTPService
from ..auth import get_current_user

router = APIRouter()
totp_service = TOTPService()


@router.get("/setup")
async def totp_setup_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        if not db_user:
            return RedirectResponse(url="/login", status_code=302)

        if db_user.totp_enabled:
            return JSONResponse(content={"message": "2FA is already enabled"})

        # Generate new secret
        secret = totp_service.generate_secret()
        uri = totp_service.get_provisioning_uri(secret, db_user.username)
        qr_base64 = totp_service.get_qr_code_base64(uri)

        return JSONResponse(content={
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_base64}",
            "uri": uri,
        })
    finally:
        db.close()


@router.post("/enable")
async def totp_enable(
    request: Request,
    secret: str = Form(...),
    code: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Verify the code against the secret
    if not totp_service.verify(secret, code):
        return JSONResponse(content={"success": False, "error": "Invalid code"}, status_code=400)

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        db_user.totp_secret = secret
        db_user.totp_enabled = True
        db.commit()
        return JSONResponse(content={"success": True})
    finally:
        db.close()


@router.post("/disable")
async def totp_disable(
    request: Request,
    code: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.id == user["id"]).first()
        if not db_user.totp_enabled:
            return JSONResponse(content={"error": "2FA is not enabled"})

        if not totp_service.verify(db_user.totp_secret, code):
            return JSONResponse(content={"success": False, "error": "Invalid code"}, status_code=400)

        db_user.totp_secret = None
        db_user.totp_enabled = False
        db.commit()
        return JSONResponse(content={"success": True})
    finally:
        db.close()
