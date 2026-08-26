"""
NexVE Ceph Service
Manages Ceph cluster, RBD pools, images, and CephFS.
"""
import subprocess
import json
from typing import List


class CephService:
    """Manages Ceph distributed storage."""

    def get_ceph_status(self) -> dict:
        """Get Ceph cluster status."""
        try:
            r = subprocess.run(
                "ceph status --format json 2>/dev/null || echo '{}'",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0 and r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    return {
                        "available": True,
                        "health": data.get("health", {}).get("status", "unknown"),
                        "fsid": data.get("fsid", ""),
                        "mon_map": data.get("mon_map", {}).get("mons", []),
                        "osd_map": {
                            "total": data.get("osd_map", {}).get("osds", []),
                            "num_osds": len(data.get("osd_map", {}).get("osds", [])),
                            "num_up": sum(1 for o in data.get("osd_map", {}).get("osds", []) if o.get("up")),
                            "num_in": sum(1 for o in data.get("osd_map", {}).get("osds", []) if o.get("in")),
                        },
                        "pg_map": data.get("pg_map", {}),
                    }
                except json.JSONDecodeError:
                    pass
            return {"available": False, "health": "unknown"}
        except Exception:
            return {"available": False, "health": "unknown"}

    def list_pools(self) -> List[dict]:
        """List RBD pools."""
        try:
            r = subprocess.run(
                "ceph osd pool ls detail --format json 2>/dev/null || echo '[]'",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                try:
                    pools = json.loads(r.stdout)
                    return [
                        {
                            "name": p.get("pool_name", ""),
                            "id": p.get("pool_id", 0),
                            "type": p.get("type", "replicated"),
                            "size": p.get("size", 1),
                            "pg_num": p.get("pg_num", 0),
                        }
                        for p in pools
                    ]
                except json.JSONDecodeError:
                    pass
            return []
        except Exception:
            return []

    def create_pool(self, name: str, pg_num: int = 128, pool_type: str = "replicated") -> dict:
        """Create a Ceph RBD pool."""
        try:
            r = subprocess.run(
                f"ceph osd pool create {name} {pg_num} {pg_num} replicated 2>/dev/null || "
                f"ceph osd pool create {name} {pg_num} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                # Enable RBD application
                subprocess.run(
                    f"ceph osd pool application enable {name} rbd 2>/dev/null || true",
                    shell=True, capture_output=True, timeout=10
                )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_pool(self, name: str) -> dict:
        """Delete a Ceph pool."""
        try:
            r = subprocess.run(
                f"ceph osd pool delete {name} {name} --yes-i-really-really-mean-it 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_images(self, pool: str = "rbd") -> List[dict]:
        """List RBD images in a pool."""
        try:
            r = subprocess.run(
                f"rbd ls {pool} --format json 2>/dev/null || echo '[]'",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                try:
                    images = json.loads(r.stdout)
                    result = []
                    for img_name in images:
                        info_r = subprocess.run(
                            f"rbd info {pool}/{img_name} --format json 2>/dev/null",
                            shell=True, capture_output=True, text=True, timeout=5
                        )
                        if info_r.returncode == 0:
                            info = json.loads(info_r.stdout)
                            result.append({
                                "name": img_name,
                                "size": info.get("size", 0),
                                "format": info.get("format", ""),
                                "pool": pool,
                            })
                        else:
                            result.append({"name": img_name, "size": 0, "pool": pool})
                    return result
                except json.JSONDecodeError:
                    pass
            return []
        except Exception:
            return []

    def create_image(self, pool: str, name: str, size_gb: int) -> dict:
        """Create an RBD image."""
        try:
            r = subprocess.run(
                f"rbd create {pool}/{name} --size {size_gb}G 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_image(self, pool: str, name: str) -> dict:
        """Delete an RBD image."""
        try:
            r = subprocess.run(
                f"rbd rm {pool}/{name} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resize_image(self, pool: str, name: str, size_gb: int) -> dict:
        """Resize an RBD image."""
        try:
            r = subprocess.run(
                f"rbd resize {pool}/{name} --size {size_gb}G 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_osd_list(self) -> List[dict]:
        """List OSDs."""
        try:
            r = subprocess.run(
                "ceph osd tree --format json 2>/dev/null || echo '{}'",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                try:
                    data = json.loads(r.stdout)
                    osds = []
                    for node in data.get("nodes", []):
                        if node.get("type") == "osd":
                            osds.append({
                                "id": node.get("id", 0),
                                "name": node.get("name", ""),
                                "status": "up" if node.get("status") == "up" else "down",
                                "weight": node.get("weight", 0),
                            })
                    return osds
                except json.JSONDecodeError:
                    pass
            return []
        except Exception:
            return []

    def list_cephfs(self) -> List[dict]:
        """List CephFS filesystems."""
        try:
            r = subprocess.run(
                "ceph fs ls --format json 2>/dev/null || echo '[]'",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                try:
                    return json.loads(r.stdout)
                except json.JSONDecodeError:
                    pass
            return []
        except Exception:
            return []
