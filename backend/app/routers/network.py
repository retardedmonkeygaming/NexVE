from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from ..services.network_service import NetworkService
from ..database import SessionLocal
from ..models.feature_models import (
    NetworkSecurityGroup, SecurityGroupRule, SecurityGroupAssignment,
    NetworkFirewallAlias, FirewallAliasEntry, NetworkRateLimit,
)
from ..auth import get_current_user, api_auth
import json

router = APIRouter()
svc = NetworkService()



@router.get("/overview")
async def network_overview(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.get_network_overview())


@router.get("/interfaces")
async def list_interfaces(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"interfaces": svc.list_interfaces()})


# ── Bridges ──

@router.get("/bridges")
async def list_bridges(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"bridges": svc.list_bridges()})


@router.post("/bridges")
async def create_bridge(request: Request, name: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.create_bridge(name)
    return JSONResponse(result)


@router.delete("/bridges/{name}")
async def delete_bridge(request: Request, name: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.delete_bridge(name)
    return JSONResponse(result)


@router.post("/bridges/{bridge}/ports")
async def add_port(request: Request, bridge: str, iface: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    result = svc.add_port(bridge, iface)
    return JSONResponse(result)


@router.delete("/bridges/{bridge}/ports/{iface}")
async def remove_port(request: Request, bridge: str, iface: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.remove_port(iface)
    return JSONResponse(result)


# ── VLANs ──

@router.get("/vlans")
async def list_vlans(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"vlans": svc.list_vlans()})


@router.post("/vlans")
async def create_vlan(request: Request, parent: str = Form(...), vlan_id: int = Form(...), name: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    result = svc.create_vlan(parent, vlan_id, name)
    return JSONResponse(result)


@router.delete("/vlans/{name}")
async def delete_vlan(request: Request, name: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.delete_vlan(name)
    return JSONResponse(result)


# ── Bonds ──

@router.get("/bonds")
async def list_bonds(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"bonds": svc.list_bonds()})


@router.post("/bonds")
async def create_bond(request: Request, name: str = Form(...), mode: str = Form("balance-rr"), slaves: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    slave_list = [s.strip() for s in slaves.split(",") if s.strip()]
    result = svc.create_bond(name, mode, slave_list)
    return JSONResponse(result)


@router.delete("/bonds/{name}")
async def delete_bond(request: Request, name: str):
    user, error = api_auth(request)
    if error: return error
    result = svc.delete_bond(name)
    return JSONResponse(result)


# ── Firewall ──

@router.get("/firewall")
async def firewall_rules(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.firewall_rules())


@router.post("/firewall/enable")
async def firewall_enable(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.firewall_enable())


@router.post("/firewall/disable")
async def firewall_disable(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.firewall_disable())


@router.post("/firewall/rules")
async def add_firewall_rule(request: Request, rule: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.firewall_add_rule(rule))



# ════════════════════════════════════════════════
# PERSISTENT NETWORK CONFIGURATION
# ════════════════════════════════════════════════

@router.get("/config")
async def get_interfaces_config(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.get_interfaces_config())

@router.post("/config")
async def save_interfaces_config(request: Request):
    user, error = api_auth(request)
    if error: return error
    body = await request.json()
    config = body.get("config", "")
    return JSONResponse(svc.save_interfaces_config(config))

@router.post("/config/apply")
async def apply_network_config(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.apply_network_config())


@router.post("/ips-restore")
async def restore_ips(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.restore_ips())


# ════════════════════════════════════════════════
# TRAFFIC MONITORING
# ════════════════════════════════════════════════

@router.get("/traffic")
async def traffic_stats(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"interfaces": svc.get_traffic_stats()})

@router.get("/gateway")
async def get_gateway(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.get_gateway_info())

@router.post("/gateway")
async def set_gateway(request: Request, gateway: str = Form(...)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.set_gateway(gateway))


# ════════════════════════════════════════════════
# SECURITY GROUPS
# ════════════════════════════════════════════════

@router.get("/security-groups")
async def list_security_groups(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        groups = db.query(NetworkSecurityGroup).all()
        result = []
        for g in groups:
            rules = db.query(SecurityGroupRule).filter(
                SecurityGroupRule.group_id == g.id
            ).order_by(SecurityGroupRule.position).all()
            result.append({
                "id": g.id,
                "name": g.name,
                "comment": g.comment,
                "enabled": g.enabled,
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
                        "position": r.position,
                    }
                    for r in rules
                ],
            })
        return JSONResponse({"security_groups": result})
    finally:
        db.close()


@router.post("/security-groups/create")
async def create_security_group(
    request: Request,
    name: str = Form(...),
    comment: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        group = NetworkSecurityGroup(name=name, comment=comment)
        db.add(group)
        db.commit()
        return JSONResponse({"success": True, "id": group.id})
    finally:
        db.close()


@router.delete("/security-groups/{group_id}")
async def delete_security_group(request: Request, group_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        db.query(SecurityGroupRule).filter(SecurityGroupRule.group_id == group_id).delete()
        db.query(SecurityGroupAssignment).filter(SecurityGroupAssignment.group_id == group_id).delete()
        db.query(NetworkSecurityGroup).filter(NetworkSecurityGroup.id == group_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/security-groups/{group_id}/rules")
async def add_security_group_rule(
    request: Request,
    group_id: int,
    direction: str = Form("in"),
    action: str = Form("accept"),
    protocol: str = Form("tcp"),
    source: str = Form(""),
    destination: str = Form(""),
    sport: str = Form(""),
    dport: str = Form(""),
    comment: str = Form(""),
    enabled: bool = Form(True),
):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        # Get next position
        max_pos = db.query(SecurityGroupRule).filter(
            SecurityGroupRule.group_id == group_id
        ).count()
        rule = SecurityGroupRule(
            group_id=group_id,
            direction=direction,
            action=action,
            protocol=protocol,
            source=source,
            destination=destination,
            sport=sport,
            dport=dport,
            comment=comment,
            enabled=enabled,
            position=max_pos,
        )
        db.add(rule)
        db.commit()
        return JSONResponse({"success": True, "id": rule.id})
    finally:
        db.close()


@router.delete("/security-groups/{group_id}/rules/{rule_id}")
async def delete_security_group_rule(request: Request, group_id: int, rule_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        db.query(SecurityGroupRule).filter(SecurityGroupRule.id == rule_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/security-groups/{group_id}/apply")
async def apply_security_group(
    request: Request,
    group_id: int,
    target_type: str = Form(""),
    target_id: int = Form(0),
):
    """Apply security group rules via nftables and optionally assign to a VM."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        group = db.query(NetworkSecurityGroup).filter(NetworkSecurityGroup.id == group_id).first()
        if not group:
            return JSONResponse({"error": "Not found"}, status_code=404)

        rules = db.query(SecurityGroupRule).filter(
            SecurityGroupRule.group_id == group_id,
            SecurityGroupRule.enabled == True,
        ).order_by(SecurityGroupRule.position).all()

        rules_data = [
            {
                "direction": r.direction,
                "action": r.action,
                "protocol": r.protocol,
                "source": r.source,
                "destination": r.destination,
                "sport": r.sport,
                "dport": r.dport,
                "log": False,
                "enabled": r.enabled,
            }
            for r in rules
        ]

        result = svc.apply_security_group(group.name, rules_data)

        # Save assignment if target specified
        if target_type and target_id:
            existing = db.query(SecurityGroupAssignment).filter(
                SecurityGroupAssignment.group_id == group_id,
                SecurityGroupAssignment.target_type == target_type,
                SecurityGroupAssignment.target_id == target_id,
            ).first()
            if not existing:
                assignment = SecurityGroupAssignment(
                    group_id=group_id,
                    target_type=target_type,
                    target_id=target_id,
                )
                db.add(assignment)
                db.commit()

        return JSONResponse(result)
    finally:
        db.close()


# ════════════════════════════════════════════════
# FIREWALL ALIASES
# ════════════════════════════════════════════════

@router.get("/aliases")
async def list_aliases(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        aliases = db.query(NetworkFirewallAlias).all()
        result = []
        for a in aliases:
            entries = db.query(FirewallAliasEntry).filter(
                FirewallAliasEntry.alias_id == a.id
            ).all()
            result.append({
                "id": a.id,
                "name": a.name,
                "type": a.alias_type,
                "comment": a.comment,
                "enabled": a.enabled,
                "entries": [e.value for e in entries],
            })
        return JSONResponse({"aliases": result})
    finally:
        db.close()


@router.post("/aliases/create")
async def create_alias(
    request: Request,
    name: str = Form(...),
    alias_type: str = Form("host"),
    comment: str = Form(""),
    entries: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        alias = NetworkFirewallAlias(name=name, alias_type=alias_type, comment=comment)
        db.add(alias)
        db.flush()

        # Add entries
        for entry in [e.strip() for e in entries.split("\n") if e.strip()]:
            db.add(FirewallAliasEntry(alias_id=alias.id, value=entry))

        db.commit()

        # Apply to nftables
        entry_list = [e.strip() for e in entries.split("\n") if e.strip()]
        if entry_list:
            svc.create_alias_set(name, entry_list)

        return JSONResponse({"success": True, "id": alias.id})
    finally:
        db.close()


@router.delete("/aliases/{alias_id}")
async def delete_alias(request: Request, alias_id: int):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        alias = db.query(NetworkFirewallAlias).filter(NetworkFirewallAlias.id == alias_id).first()
        if alias:
            svc.delete_alias_set(alias.name)
            db.query(FirewallAliasEntry).filter(FirewallAliasEntry.alias_id == alias_id).delete()
            db.query(NetworkFirewallAlias).filter(NetworkFirewallAlias.id == alias_id).delete()
            db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


# ════════════════════════════════════════════════
# RATE LIMITING
# ════════════════════════════════════════════════

@router.get("/rate-limits")
async def list_rate_limits(request: Request):
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        limits = db.query(NetworkRateLimit).all()
        result = []
        for l in limits:
            result.append({
                "id": l.id,
                "interface": l.interface,
                "rx_bytes": l.rx_bytes,
                "tx_bytes": l.tx_bytes,
                "rx_burst": l.rx_burst,
                "tx_burst": l.tx_burst,
                "enabled": l.enabled,
            })
        return JSONResponse({"rate_limits": result})
    finally:
        db.close()


@router.post("/rate-limits")
async def set_rate_limit(
    request: Request,
    interface: str = Form(...),
    rx_bytes: str = Form(""),
    tx_bytes: str = Form(""),
    rx_burst: str = Form(""),
    tx_burst: str = Form(""),
):
    user, error = api_auth(request)
    if error: return error

    rx = int(rx_bytes) if rx_bytes else None
    tx = int(tx_bytes) if tx_bytes else None
    rxb = int(rx_burst) if rx_burst else None
    txb = int(tx_burst) if tx_burst else None

    result = svc.set_interface_rate_limit(interface, rx, tx, rxb, txb)

    # Save to DB
    db = SessionLocal()
    try:
        existing = db.query(NetworkRateLimit).filter(
            NetworkRateLimit.interface == interface
        ).first()
        if existing:
            existing.rx_bytes = rx
            existing.tx_bytes = tx
            existing.rx_burst = rxb
            existing.tx_burst = txb
            existing.enabled = True
        else:
            limit = NetworkRateLimit(
                interface=interface,
                rx_bytes=rx,
                tx_bytes=tx,
                rx_burst=rxb,
                tx_burst=txb,
            )
            db.add(limit)
        db.commit()
    finally:
        db.close()

    return JSONResponse(result)


@router.delete("/rate-limits/{interface}")
async def clear_rate_limit(request: Request, interface: str):
    user, error = api_auth(request)
    if error: return error
    svc.clear_interface_rate_limit(interface)
    db = SessionLocal()
    try:
        db.query(NetworkRateLimit).filter(NetworkRateLimit.interface == interface).delete()
        db.commit()
    finally:
        db.close()
    return JSONResponse({"success": True})


# ════════════════════════════════════════════════
# STP (Spanning Tree Protocol)
# ════════════════════════════════════════════════

@router.get("/stp/status")
async def stp_status(request: Request, bridge: str = "vmbr0"):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.stp_status(bridge))


@router.post("/stp/enable")
async def stp_enable(request: Request, bridge: str = Form("vmbr0"), priority: int = Form(32768)):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.stp_enable(bridge, priority))


@router.post("/stp/disable")
async def stp_disable(request: Request, bridge: str = Form("vmbr0")):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.stp_disable(bridge))


# ════════════════════════════════════════════════
# BOND MODES
# ════════════════════════════════════════════════

@router.get("/bond/modes")
async def list_bond_modes(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse({"modes": svc.list_bond_modes()})


@router.get("/bond/{name}/status")
async def bond_status(name: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.get_bond_status(name))


# ════════════════════════════════════════════════
# MIGRATION NETWORK
# ════════════════════════════════════════════════

@router.get("/migration-network")
async def get_migration_network(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.get_migration_network())


@router.post("/migration-network")
async def set_migration_network(request: Request, interface: str = Form(...),
                                cidr: str = Form(""), gateway: str = Form("")):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.set_migration_network(interface, cidr, gateway))


@router.delete("/migration-network")
async def disable_migration_network(request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.disable_migration_network())


# ════════════════════════════════════════════════
# INTERFACE TRAFFIC
# ════════════════════════════════════════════════

@router.get("/interface/{name}/traffic")
async def interface_traffic(name: str, request: Request):
    user, error = api_auth(request)
    if error: return error
    return JSONResponse(svc.get_interface_traffic(name))
