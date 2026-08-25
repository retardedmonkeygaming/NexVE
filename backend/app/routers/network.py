from fastapi import APIRouter
import psutil

router = APIRouter()

@router.get("/")
async def list_interfaces():
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    io = psutil.net_io_counters(pernic=True)
    
    interfaces = []
    for name in addrs:
        interfaces.append({
            "name": name,
            "addresses": [a._asdict() for a in addrs[name]],
            "is_up": stats[name].isup if name in stats else False,
            "bytes_sent": io[name].bytes_sent if name in io else 0,
            "bytes_recv": io[name].bytes_recv if name in io else 0
        })
    return {"interfaces": interfaces}
