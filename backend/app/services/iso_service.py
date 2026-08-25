import os
import subprocess
from typing import List

ISO_DIR = "/var/lib/nexve/iso"


class ISOService:
    def __init__(self):
        os.makedirs(ISO_DIR, exist_ok=True)

    def list_local(self) -> List[dict]:
        isos = []
        for f in os.listdir(ISO_DIR):
            if f.endswith((".iso", ".img")):
                path = os.path.join(ISO_DIR, f)
                size = os.path.getsize(path) / (1024**3)
                isos.append({"name": f, "filename": f, "size_gb": round(size, 2), "path": path})
        return isos

    def download(self, url: str, name: str = "") -> dict:
        filename = name or url.split("/")[-1]
        dest = os.path.join(ISO_DIR, filename)
        if os.path.exists(dest):
            return {"success": False, "error": "File already exists"}
        try:
            r = subprocess.run(
                ["wget", "-q", "--show-progress", "-O", dest, url],
                capture_output=True, text=True, timeout=3600
            )
            return {"success": r.returncode == 0, "stderr": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Download timed out"}

    def delete(self, filename: str) -> dict:
        path = os.path.join(ISO_DIR, filename)
        if os.path.exists(path):
            os.remove(path)
            return {"success": True}
        return {"success": False, "error": "File not found"}

    def get_path(self, filename: str) -> str:
        return os.path.join(ISO_DIR, filename)
