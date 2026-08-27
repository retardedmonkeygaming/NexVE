"""
NexVE ISO Service v3.0
Manages ISO images with proper path handling.
"""
import os
import subprocess
from typing import List
from datetime import datetime

# Use user-writable path for development, system path for production
ISO_DIR = os.path.expanduser("~/.nexve/iso")
if os.path.exists("/var/lib/nexve/iso"):
    ISO_DIR = "/var/lib/nexve/iso"


class ISOService:
    def __init__(self):
        os.makedirs(ISO_DIR, exist_ok=True)

    @property
    def ISO_DIR(self):
        return ISO_DIR

    def list_local(self) -> List[dict]:
        isos = []
        try:
            for f in sorted(os.listdir(ISO_DIR)):
                path = os.path.join(ISO_DIR, f)
                if os.path.isfile(path) and f.endswith((".iso", ".img", ".qcow2", ".raw")):
                    size = os.path.getsize(path) / (1024**3)
                    stat = os.stat(path)
                    isos.append({
                        "name": f,
                        "filename": f,
                        "size_gb": round(size, 2),
                        "size_bytes": stat.st_size,
                        "path": path,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
        except Exception:
            pass
        return isos

    def download(self, url: str, name: str = "") -> dict:
        filename = name or url.split("/")[-1]
        dest = os.path.join(ISO_DIR, filename)
        if os.path.exists(dest):
            return {"success": False, "error": "File already exists"}
        try:
            r = subprocess.run(
                ["wget", "-q", "-O", dest, url],
                capture_output=True, text=True, timeout=3600
            )
            if r.returncode != 0:
                # Fallback to curl
                r2 = subprocess.run(
                    ["curl", "-sL", "-o", dest, url],
                    capture_output=True, text=True, timeout=3600
                )
                return {"success": r2.returncode == 0, "stderr": r2.stderr.strip()}
            return {"success": True, "filename": filename}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Download timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, filename: str) -> dict:
        path = os.path.join(ISO_DIR, filename)
        if os.path.exists(path) and os.path.isfile(path):
            os.remove(path)
            return {"success": True}
        return {"success": False, "error": "File not found"}

    def get_path(self, filename: str) -> str:
        return os.path.join(ISO_DIR, filename)

    def get_info(self, filename: str) -> dict:
        path = os.path.join(ISO_DIR, filename)
        if not os.path.exists(path):
            return {"error": "File not found"}
        stat = os.stat(path)
        return {
            "name": filename,
            "path": path,
            "size_bytes": stat.st_size,
            "size_gb": round(stat.st_size / (1024**3), 2),
            "exists": True,
        }
