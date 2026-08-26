from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.firewall import FirewallRule, FirewallGroup
from ..services.firewall_service import FirewallService
from ..auth import get_current_user

router = APIRouter()
fw_service = FirewallService()


def auth_check(request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


# ── Firewall rules API (JSON) ──

@router.get("/rules")
async def list_rules(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        rules = db.query(FirewallRule).order_by(FirewallRule.position).all()
        groups = db.query(FirewallGroup).all()
        return JSONResponse({
            "rules": [
                {
                    "id": r.id,
                    "direction": r.direction,
                    "action": r.action,
                    "protocol": r.protocol,
                    "source": r.source,
                    "destination": r.destination,
                    "sport": r.sport,
                    "dport": r.dport,
                    "comment": r.comment,
                    "enabled": r.enabled,
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "log": r.log,
                    "position": r.position,
                }
                for r in rules
            ],
            "groups": [
                {"id": g.id, "name": g.name, "comment": g.comment}
                for g in groups
            ],
        })
    finally:
        db.close()


@router.post("/rules/create")
async def create_rule(
    request: Request,
    direction: str = Form(...),
    action: str = Form(...),
    protocol: str = Form("tcp"),
    source: str = Form(""),
    destination: str = Form(""),
    sport: str = Form(""),
    dport: str = Form(""),
    target_type: str = Form("host"),
    target_id: str = Form(""),
    comment: str = Form(""),
    position: int = Form(0),
    enabled: bool = Form(True),
    log: bool = Form(False),
):
    user, redir = auth_check(request)
    if redir:
        return redir

    db = SessionLocal()
    try:
        rule = FirewallRule(
            direction=direction, action=action, protocol=protocol,
            source=source, destination=destination, sport=sport, dport=dport,
            target_type=target_type, target_id=target_id, comment=comment,
            position=position, enabled=enabled, log=log
        )
        db.add(rule)
        db.commit()
        fw_service.apply_rules(db, target_type, target_id)
        return JSONResponse({"success": True, "id": rule.id})
    finally:
        db.close()


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int, request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        rule = db.query(FirewallRule).filter(FirewallRule.id == rule_id).first()
        if rule:
            tt, ti = rule.target_type, rule.target_id
            db.delete(rule)
            db.commit()
            fw_service.apply_rules(db, tt, ti)
    finally:
        db.close()
    return JSONResponse({"success": True})


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: int, request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        rule = db.query(FirewallRule).filter(FirewallRule.id == rule_id).first()
        if rule:
            rule.enabled = not rule.enabled
            db.commit()
            fw_service.apply_rules(db, rule.target_type, rule.target_id)
    finally:
        db.close()
    return JSONResponse({"success": True})


# ── Firewall groups ──

@router.get("/groups")
async def list_groups(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        groups = db.query(FirewallGroup).all()
        return JSONResponse({
            "groups": [
                {"id": g.id, "name": g.name, "comment": g.comment}
                for g in groups
            ]
        })
    finally:
        db.close()


@router.post("/groups/create")
async def create_group(
    request: Request,
    name: str = Form(...),
    comment: str = Form(""),
):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        group = FirewallGroup(name=name, comment=comment)
        db.add(group)
        db.commit()
        return JSONResponse({"success": True, "id": group.id})
    finally:
        db.close()


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int, request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        db.query(FirewallGroup).filter(FirewallGroup.id == group_id).delete()
        db.commit()
    finally:
        db.close()
    return JSONResponse({"success": True})


# ── Apply / Stats ──

@router.post("/apply")
async def apply_all_rules(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    db = SessionLocal()
    try:
        fw_service.apply_rules(db, "host", "")
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.get("/stats")
async def firewall_stats(request: Request):
    user, redir = auth_check(request)
    if redir:
        return redir
    return JSONResponse(fw_service.get_stats())
