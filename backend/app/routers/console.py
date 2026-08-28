"""
NexVE Console Router
API endpoints for VM/container console access (VNC, SPICE, serial, xterm.js).
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from ..services.console_service import ConsoleService
from ..services.vm_service import VMService
from ..database import SessionLocal
from ..models.vm import VM
from ..auth import get_current_user, api_auth

router = APIRouter()
console_svc = ConsoleService()
vm_svc = VMService()



@router.get("/types/{vm_id}")
async def get_console_types(vm_id: int, request: Request):
    """Get available console types for a VM."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)
        types = console_svc.get_console_types(vm.name)
        return JSONResponse({"types": types})
    finally:
        db.close()


@router.get("/vnc/{vm_id}")
async def get_vnc_info(vm_id: int, request: Request):
    """Get VNC connection info for a VM."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)
        info = console_svc.get_vnc_info(vm.name)
        return JSONResponse(info)
    finally:
        db.close()


@router.post("/vnc/{vm_id}/start")
async def start_vnc_proxy(vm_id: int, request: Request):
    """Start VNC websockify proxy."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)
        vnc_info = console_svc.get_vnc_info(vm.name)
        if not vnc_info.get("available"):
            return JSONResponse(vnc_info)
        result = console_svc.start_websockify(vm.name, vnc_info["port"])
        return JSONResponse(result)
    finally:
        db.close()


@router.post("/vnc/{vm_id}/stop")
async def stop_vnc_proxy(vm_id: int, request: Request):
    """Stop VNC websockify proxy."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)
        result = console_svc.stop_websockify(vm.name)
        return JSONResponse(result)
    finally:
        db.close()


@router.get("/spice/{vm_id}")
async def get_spice_info(vm_id: int, request: Request):
    """Get SPICE connection info for a VM."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)
        info = console_svc.get_spice_info(vm.name)
        return JSONResponse(info)
    finally:
        db.close()


@router.get("/serial/{vm_id}")
async def get_serial_info(vm_id: int, request: Request):
    """Get serial console info for a VM."""
    user, error = api_auth(request)
    if error: return error
    db = SessionLocal()
    try:
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            return JSONResponse({"error": "VM not found"}, status_code=404)
        info = console_svc.get_serial_info(vm.name)
        return JSONResponse(info)
    finally:
        db.close()


@router.get("/container/{ct_id}")
async def get_container_console(ct_id: int, request: Request):
    """Get container console info."""
    user, error = api_auth(request)
    if error: return error
    info = console_svc.get_container_console(ct_id)
    return JSONResponse(info)
