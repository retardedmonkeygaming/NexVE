"""
NexVE Datacenter Settings Router
Proxmox-equivalent: Datacenter → Options, Firewall, Authentication
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse
from ..database import SessionLocal
from ..models.feature_models import DatacenterSettings, DatacenterFirewallRule, WebAuthnCredential
from ..models.user import User
from ..auth import api_auth
from ..task_utils import log_task
import json

router = APIRouter()

# ── Default datacenter settings (Proxmox-equivalent) ──
DEFAULTS = {
    "console": "html5",  # html5, vnc, spice, xtermjs
    "keyboard": "en-us",
    "language": "en",
    "http_proxy": "",
    "mac_prefix": "BC:24:11",
    "next_id_lower": "100",
    "next_id_upper": "1000000",
    "max_workers": "10",
    "description": "",
    "latitude": "0",
    "longitude": "0",
    "location_name": "",
    "migration_type": "secure",
    "migration_network": "",
    "replication_type": "secure",
    "replication_network": "",
    "bwlimit_default": "0",
    "bwlimit_clone": "0",
    "bwlimit_migration": "0",
    "bwlimit_move": "0",
    "bwlimit_restore": "0",
    "crs_ha": "basic",  # basic, static, dynamic
    "ha_shutdown_policy": "conditional",  # conditional, failover, freeze, migrate
    "fencing_mode": "watchdog",  # watchdog, hardware, both
    "consent_text": "",
    "tag_case_sensitive": "0",
    "tag_ordering": "alphabetical",
    "tag_shape": "circle",
    "user_tag_access": "free",
}


def _get_setting(db, key, default=None):
    s = db.query(DatacenterSettings).filter(DatacenterSettings.key == key).first()
    return s.value if s else (default or DEFAULTS.get(key, ""))


def _set_setting(db, key, value, description=None):
    s = db.query(DatacenterSettings).filter(DatacenterSettings.key == key).first()
    if s:
        s.value = str(value)
        if description:
            s.description = description
    else:
        s = DatacenterSettings(key=key, value=str(value), description=description)
        db.add(s)
    db.commit()


# ── GET all datacenter settings ──
@router.get("/settings")
async def get_datacenter_settings(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        settings = {}
        for key, default in DEFAULTS.items():
            settings[key] = _get_setting(db, key, default)
        return JSONResponse({"settings": settings})
    finally:
        db.close()


# ── POST update datacenter settings ──
@router.post("/settings")
async def update_datacenter_settings(request: Request):
    user, error = api_auth(request)
    if error: return error
    if not user or user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)
    db = SessionLocal()
    try:
        form = await request.form()
        for key in DEFAULTS:
            if key in form:
                _set_setting(db, key, form[key])
        log_task(user.id, user.username, "datacenter.settings.update", "datacenter", "settings", "completed")
        return JSONResponse({"success": True})
    finally:
        db.close()


# ── Datacenter Firewall ──
@router.get("/firewall/rules")
async def list_dc_firewall_rules(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        rules = db.query(DatacenterFirewallRule).order_by(DatacenterFirewallRule.pos).all()
        return JSONResponse({"rules": [
            {
                "id": r.id, "action": r.action, "direction": r.direction,
                "protocol": r.protocol, "source": r.source, "destination": r.destination,
                "dport": r.dport, "comment": r.comment, "enabled": r.enabled, "pos": r.pos,
            } for r in rules
        ]})
    finally:
        db.close()


@router.post("/firewall/rules")
async def create_dc_firewall_rule(
    request: Request,
    action: str = Form("accept"),
    direction: str = Form("in"),
    protocol: str = Form("tcp"),
    source: str = Form(""),
    destination: str = Form(""),
    dport: str = Form(""),
    comment: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        max_pos = db.query(DatacenterFirewallRule).count()
        rule = DatacenterFirewallRule(
            action=action, direction=direction, protocol=protocol,
            source=source or None, destination=destination or None,
            dport=dport or None, comment=comment or None, pos=max_pos,
        )
        db.add(rule)
        db.commit()
        log_task(user.id, user.username, "dc.firewall.create", "firewall", comment or dport, "completed")
        return JSONResponse({"success": True, "id": rule.id})
    finally:
        db.close()


@router.delete("/firewall/rules/{rule_id}")
async def delete_dc_firewall_rule(rule_id: int, request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        rule = db.query(DatacenterFirewallRule).filter(DatacenterFirewallRule.id == rule_id).first()
        if rule:
            db.delete(rule)
            db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


# ── WebAuthn ──
@router.get("/webauthn/credentials")
async def list_webauthn_credentials(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        creds = db.query(WebAuthnCredential).filter(
            WebAuthnCredential.user_id == user.id
        ).all()
        return JSONResponse({"credentials": [
            {"id": c.id, "device_name": c.device_name or "Security Key",
             "created_at": c.created_at.isoformat() if c.created_at else None,
             "last_used": c.last_used.isoformat() if c.last_used else None}
            for c in creds
        ]})
    finally:
        db.close()


@router.post("/webauthn/register/begin")
async def webauthn_register_begin(request: Request):
    """Begin WebAuthn registration — generate challenge."""
    user, error = api_auth(request)
    if error: return error
    import os, base64
    challenge = base64.urlsafe_b64encode(os.urandom(32)).decode()
    return JSONResponse({
        "challenge": challenge,
        "rp": {"name": "NexVE", "id": request.hostname},
        "user": {"id": str(user.id), "name": user.username, "displayName": user.username},
    })


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(request: Request):
    """Complete WebAuthn registration — store credential."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        body = await request.json()
        cred = WebAuthnCredential(
            user_id=user.id,
            credential_id=body.get("credential_id", ""),
            public_key=body.get("public_key", ""),
            device_name=body.get("device_name", "Security Key"),
        )
        db.add(cred)
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.delete("/webauthn/credentials/{cred_id}")
async def delete_webauthn_credential(cred_id: int, request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        cred = db.query(WebAuthnCredential).filter(
            WebAuthnCredential.id == cred_id,
            WebAuthnCredential.user_id == user.id,
        ).first()
        if cred:
            db.delete(cred)
            db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


# ── Node Lifecycle (reboot/shutdown) ──
@router.post("/nodes/{node_id}/reboot")
async def reboot_node(node_id: int, request: Request):
    user, error = api_auth(request)
    if error: return error
    if not user or user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)
    import subprocess
    log_task(user.id, user.username, "node.reboot", "node", str(node_id), "completed")
    try:
        subprocess.Popen(["shutdown", "-r", "+0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
    return JSONResponse({"success": True, "message": "Reboot scheduled"})


@router.post("/nodes/{node_id}/shutdown")
async def shutdown_node(node_id: int, request: Request):
    user, error = api_auth(request)
    if error: return error
    if not user or user.role != "admin":
        return JSONResponse({"success": False, "error": "Admin only"}, status_code=403)
    import subprocess
    log_task(user.id, user.username, "node.shutdown", "node", str(node_id), "completed")
    try:
        subprocess.Popen(["shutdown", "-h", "+0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
    return JSONResponse({"success": True, "message": "Shutdown scheduled"})


# ── Consent Banner ──
@router.get("/consent")
async def get_consent():
    """Public endpoint — no auth needed."""
    db = SessionLocal()
    try:
        text = _get_setting(db, "consent_text", "")
        return JSONResponse({"text": text, "enabled": bool(text)})
    finally:
        db.close()
