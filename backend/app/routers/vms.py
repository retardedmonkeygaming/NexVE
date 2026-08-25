from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_vms():
    # Placeholder — will connect to libvirt later
    return {"vms": []}

@router.post("/")
async def create_vm():
    return {"status": "not yet implemented"}

@router.get("/{vm_id}")
async def get_vm(vm_id: int):
    return {"vm_id": vm_id, "status": "not yet implemented"}
