from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_users():
    return {"users": [{"name": "precision", "role": "admin"}]}

@router.post("/login")
async def login():
    return {"status": "not yet implemented"}
