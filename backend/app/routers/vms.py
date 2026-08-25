from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from ..database import get_db
from ..services.vm_service import vm_service

router = APIRouter()

class VMCreate(BaseModel):
    name: str
    vcpu: int = 2
    memory_mb: int = 2048
    disk_gb: int = 50

class VMResponse(BaseModel):
    id: int
    name: str
    status: str
    vcpu: int
    memory_mb: int
    disk_gb: int
    ip_address: Optional[str] = None

@router.get("/")
async def list_vms(db: Session = Depends(get_db)):
    vms = vm_service.get_all_vms(db)
    return {"vms": vms}

@router.post("/")
async def create_vm(vm: VMCreate, db: Session = Depends(get_db)):
    try:
        result = vm_service.create_vm(db, vm.name, vm.vcpu, vm.memory_mb, vm.disk_gb)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{vm_id}/start")
async def start_vm(vm_id: int, db: Session = Depends(get_db)):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    
    success = vm_service.start_vm(vm.name)
    if success:
        vm.status = "running"
        db.commit()
        return {"status": "started"}
    raise HTTPException(status_code=500, detail="Failed to start VM")

@router.post("/{vm_id}/stop")
async def stop_vm(vm_id: int, db: Session = Depends(get_db)):
    vm = db.query(VM).filter(VM.id == vm_id).first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    
    success = vm_service.stop_vm(vm.name)
    if success:
        vm.status = "stopped"
        db.commit()
        return {"status": "stopped"}
    raise HTTPException(status_code=500, detail="Failed to stop VM")

@router.delete("/{vm_id}")
async def delete_vm(vm_id: int, db: Session = Depends(get_db)):
    success = vm_service.delete_vm(db, vm_id)
    if success:
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="VM not found")
