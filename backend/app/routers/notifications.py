"""
NexVE Notifications Router
API endpoints for notification target and rule management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.enhanced_models import NotificationTarget, NotificationRule
from ..services.notification_service import NotificationService
from ..auth import get_current_user

router = APIRouter()
notif_svc = NotificationService()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


# ── Notification Targets ──

@router.get("/targets")
async def list_targets(request: Request):
    """List notification targets."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        targets = db.query(NotificationTarget).all()
        return JSONResponse({"targets": [
            {
                "id": t.id, "name": t.name, "target_type": t.target_type,
                "enabled": t.enabled,
            }
            for t in targets
        ]})
    finally:
        db.close()


@router.post("/targets")
async def create_target(
    request: Request,
    name: str = Form(...),
    target_type: str = Form(...),
    config_json: str = Form("{}"),
):
    """Create a notification target."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        target = NotificationTarget(
            name=name, target_type=target_type, config_json=config_json,
        )
        db.add(target)
        db.commit()
        return JSONResponse({"success": True, "id": target.id})
    finally:
        db.close()


@router.delete("/targets/{target_id}")
async def delete_target(target_id: int, request: Request):
    """Delete a notification target."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        db.query(NotificationTarget).filter(NotificationTarget.id == target_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/targets/{target_id}/toggle")
async def toggle_target(target_id: int, request: Request):
    """Toggle notification target enabled/disabled."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
        if target:
            target.enabled = not target.enabled
            db.commit()
        return JSONResponse({"success": True, "enabled": target.enabled if target else False})
    finally:
        db.close()


@router.post("/test")
async def test_notification(
    request: Request,
    target_id: int = Form(...),
):
    """Send a test notification."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
        if not target:
            return JSONResponse({"error": "Target not found"}, status_code=404)

        import json
        config = json.loads(target.config_json) if target.config_json else {}
        result = notif_svc.test_notification(target.target_type, config)
        return JSONResponse(result)
    finally:
        db.close()


# ── Notification Rules ──

@router.get("/rules")
async def list_rules(request: Request):
    """List notification rules."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        rules = db.query(NotificationRule).all()
        return JSONResponse({"rules": [
            {
                "id": r.id, "name": r.name, "target_id": r.target_id,
                "event_types": r.event_types, "severity": r.severity,
                "enabled": r.enabled,
            }
            for r in rules
        ]})
    finally:
        db.close()


@router.post("/rules")
async def create_rule(
    request: Request,
    name: str = Form(...),
    target_id: int = Form(...),
    event_types: str = Form("[]"),
    severity: str = Form("warning"),
):
    """Create a notification rule."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        rule = NotificationRule(
            name=name, target_id=target_id,
            event_types=event_types, severity=severity,
        )
        db.add(rule)
        db.commit()
        return JSONResponse({"success": True, "id": rule.id})
    finally:
        db.close()


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int, request: Request):
    """Delete a notification rule."""
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        db.query(NotificationRule).filter(NotificationRule.id == rule_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()
