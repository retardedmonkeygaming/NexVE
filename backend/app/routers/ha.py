"""
NexVE HA Router
API endpoints for High Availability management.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..database import SessionLocal
from ..models.enhanced_models import HAGroup, HAGuest
from ..services.ha_service import HAService
from ..auth import get_current_user, api_auth

router = APIRouter()
ha_svc = HAService()



@router.get("/status")
async def ha_status(request: Request):
    """Get HA cluster status."""
    user, error = api_auth(request)
    if error: return error
    status = ha_svc.get_ha_status()
    resources = ha_svc.get_ha_resources()
    return JSONResponse({**status, "resources": resources})


@router.get("/groups")
async def list_groups(request: Request):
    """List HA groups."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        groups = db.query(HAGroup).all()
        return JSONResponse({"groups": [
            {
                "id": g.id, "name": g.name, "description": g.description,
                "nodes": g.nodes, "strategy": g.strategy,
                "max_restart": g.max_restart, "enabled": g.enabled,
            }
            for g in groups
        ]})
    finally:
        db.close()


@router.post("/groups")
async def create_group(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    nodes: str = Form(""),
    strategy: str = Form("failover"),
    max_restart: int = Form(3),
):
    """Create an HA group."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        group = HAGroup(
            name=name, description=description, nodes=nodes,
            strategy=strategy, max_restart=max_restart,
        )
        db.add(group)
        db.commit()
        return JSONResponse({"success": True, "id": group.id})
    finally:
        db.close()


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int, request: Request):
    """Delete an HA group."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        db.query(HAGroup).filter(HAGroup.id == group_id).delete()
        db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.get("/guests")
async def list_ha_guests(request: Request):
    """List HA-managed guests."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        guests = db.query(HAGuest).all()
        return JSONResponse({"guests": [
            {
                "id": g.id, "target_type": g.target_type,
                "target_id": g.target_id, "target_name": g.target_name,
                "group_id": g.group_id, "state": g.state,
                "priority": g.priority, "current_node": g.current_node,
                "enabled": g.enabled,
            }
            for g in guests
        ]})
    finally:
        db.close()


@router.post("/guests")
async def add_ha_guest(
    request: Request,
    target_type: str = Form(...),
    target_id: int = Form(...),
    target_name: str = Form(""),
    group_id: int = Form(0),
    priority: int = Form(0),
    max_restart: int = Form(3),
):
    """Add a guest to HA management."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        guest = HAGuest(
            target_type=target_type, target_id=target_id,
            target_name=target_name, group_id=group_id or None,
            priority=priority,
        )
        db.add(guest)
        db.commit()

        # Also add to system HA manager
        result = ha_svc.add_ha_resource(target_id, target_type, 
                                        group=str(group_id) if group_id else "",
                                        max_restart=max_restart)
        return JSONResponse({"success": True, "id": guest.id, "ha": result})
    finally:
        db.close()


@router.delete("/guests/{guest_id}")
async def remove_ha_guest(guest_id: int, request: Request):
    """Remove a guest from HA."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        guest = db.query(HAGuest).filter(HAGuest.id == guest_id).first()
        if guest:
            ha_svc.remove_ha_resource(guest.target_id, guest.target_type)
            db.delete(guest)
            db.commit()
        return JSONResponse({"success": True})
    finally:
        db.close()


@router.post("/guests/{guest_id}/restart")
async def ha_restart_guest(guest_id: int, request: Request):
    """Request HA restart for a guest."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        guest = db.query(HAGuest).filter(HAGuest.id == guest_id).first()
        if not guest:
            return JSONResponse({"error": "Guest not found"}, status_code=404)
        result = ha_svc.ha_restart(guest.target_id, guest.target_type)
        return JSONResponse(result)
    finally:
        db.close()


@router.post("/guests/{guest_id}/migrate")
async def ha_migrate_guest(
    guest_id: int,
    request: Request,
    target_node: str = Form(...),
):
    """Migrate an HA guest to another node."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        guest = db.query(HAGuest).filter(HAGuest.id == guest_id).first()
        if not guest:
            return JSONResponse({"error": "Guest not found"}, status_code=404)
        result = ha_svc.migrate_resource(guest.target_id, target_node, guest.target_type)
        return JSONResponse(result)
    finally:
        db.close()
