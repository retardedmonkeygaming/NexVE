import subprocess
import os
import json
from typing import List, Optional, Dict


class StorageService:
    """Manages local and remote storage backends via CLI commands."""

    def run_cmd(self, cmd: str) -> dict:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out"}

    # ──────────────────────────────────────────────
    # ZFS
    # ──────────────────────────────────────────────

    def zfs_list_pools(self) -> List[dict]:
        r = self.run_cmd("zpool list -H -o name,size,used,avail,cap,health -J")
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            return [
                {
                    "name": p["name"],
                    "size": p.get("size", "0"),
                    "used": p.get("used", "0"),
                    "avail": p.get("avail", "0"),
                    "capacity": p.get("cap", "0"),
                    "health": p.get("health", "UNKNOWN"),
                }
                for p in data
            ]
        except json.JSONDecodeError:
            return []

    def zfs_create_pool(self, name: str, device: str, force: bool = False) -> dict:
        force_flag = "-f" if force else ""
        return self.run_cmd(f"zpool create {force_flag} {name} {device}")

    def zfs_destroy_pool(self, name: str) -> dict:
        return self.run_cmd(f"zpool destroy -f {name}")

    def zfs_list_volumes(self, pool: str = "") -> List[dict]:
        cmd = "zfs list -H -o name,size,used,avail,mountpoint,type -t volume,filesystem -J"
        if pool:
            cmd = f"zfs list -H -o name,size,used,avail,mountpoint,type -t volume,filesystem {pool} -J"
        r = self.run_cmd(cmd)
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def zfs_create_volume(self, pool: str, name: str, size_gb: int) -> dict:
        return self.run_cmd(f"zfs create -V {size_gb}G {pool}/{name}")

    def zfs_create_dataset(self, pool: str, name: str) -> dict:
        return self.run_cmd(f"zfs create {pool}/{name}")

    def zfs_destroy(self, volume: str) -> dict:
        return self.run_cmd(f"zfs destroy -rf {volume}")

    def zfs_snapshots(self, volume: str) -> List[dict]:
        r = self.run_cmd(f"zfs list -t snapshot -H -o name,used,refer,creation -J {volume}")
        if not r["success"]:
            return []
        try:
            return json.loads(r["stdout"]) if isinstance(json.loads(r["stdout"]), list) else []
        except json.JSONDecodeError:
            return []

    def zfs_snapshot(self, volume: str, snap_name: str) -> dict:
        return self.run_cmd(f"zfs snapshot {volume}@{snap_name}")

    def zfs_scrub(self, pool: str) -> dict:
        return self.run_cmd(f"zpool scrub {pool}")

# ──────────────────────────────────────────────
# iSCSI
# ──────────────────────────────────────────────

def iscsi_discover(self, target: str, port: int = 3260) -> List[dict]:
    r = self.run_cmd(f"iscsiadm -m discovery -t sendtargets -p {target}:{port}")
    if not r["success"]:
        return []
    targets = []
    for line in r["stdout"].splitlines():
        parts = line.strip().split(",")
        if len(parts) >= 2:
            targets.append({"address": parts[0].strip(), "target": parts[1].strip()})
    return targets

def iscsi_login(self, target: str, portal: str, port: int = 3260) -> dict:
    self.run_cmd(f"iscsiadm -m node -T {target} -p {portal}:{port} --login")
    return self.run_cmd(f"iscsiadm -m session")

def iscsi_logout(self, target: str) -> dict:
    return self.run_cmd(f"iscsiadm -m node -T {target} --logout")

def iscsi_list_sessions(self) -> List[dict]:
    r = self.run_cmd("iscsiadm -m session -P 1")
    sessions = []
    for line in r["stdout"].splitlines():
        if "Non-leading" in line or "iSCSI" in line:
            sessions.append({"info": line.strip()})
    return sessions

def iscsi_delete_node(self, target: str, portal: str) -> dict:
    return self.run_cmd(f"iscsiadm -m node -T {target} -p {portal} -o delete")


    # ──────────────────────────────────────────────
    # LVM
    # ──────────────────────────────────────────────

    def lvm_list_vgs(self) -> List[dict]:
        r = self.run_cmd("vgs --reportformat json")
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            vgs = data.get("report", [{}])[0].get("vg", [])
            return [
                {
                    "name": vg.get("vg_name"),
                    "size": vg.get("vg_size", "0"),
                    "free": vg.get("vg_free", "0"),
                    "used": float(vg.get("vg_size", "0").replace("g", "").replace("G", "0") or 0)
                           - float(vg.get("vg_free", "0").replace("g", "").replace("G", "0") or 0),
                    "pv_count": int(vg.get("pv_count", 0)),
                    "lv_count": int(vg.get("lv_count", 0)),
                }
                for vg in vgs
            ]
        except (json.JSONDecodeError, IndexError):
            return []

    def lvm_list_lvs(self, vg_name: str = "") -> List[dict]:
        cmd = "lvs --reportformat json"
        if vg_name:
            cmd += f" {vg_name}"
        r = self.run_cmd(cmd)
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            lvs = data.get("report", [{}])[0].get("lv", [])
            return [
                {
                    "name": lv.get("lv_name"),
                    "vg": lv.get("vg_name"),
                    "size": lv.get("lv_size"),
                    "type": lv.get("lv_attr", "")[:1],
                }
                for lv in lvs
            ]
        except (json.JSONDecodeError, IndexError):
            return []

    def lvm_create_vg(self, name: str, device: str) -> dict:
        return self.run_cmd(f"pvcreate {device} && vgcreate {name} {device}")

    def lvm_remove_vg(self, name: str) -> dict:
        return self.run_cmd(f"vgremove -f {name}")

    def lvm_create_lv(self, vg_name: str, lv_name: str, size_gb: int) -> dict:
        return self.run_cmd(f"lvcreate -L {size_gb}G -n {lv_name} {vg_name}")

    def lvm_remove_lv(self, lv_path: str) -> dict:
        return self.run_cmd(f"lvremove -f {lv_path}")

    # ──────────────────────────────────────────────
    # Directory-based storage
    # ──────────────────────────────────────────────

    def dir_check(self, path: str) -> dict:
        return {
            "exists": os.path.isdir(path),
            "path": path,
            "contents": os.listdir(path) if os.path.isdir(path) else [],
        }

    def dir_usage(self, path: str) -> dict:
        try:
            stat = os.statvfs(path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            return {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "available_gb": round(free / (1024**3), 2),
                "percent": round((used / total) * 100, 1) if total > 0 else 0,
            }
        except OSError:
            return {"total_gb": 0, "used_gb": 0, "available_gb": 0, "percent": 0}

    # ──────────────────────────────────────────────
    # NFS
    # ──────────────────────────────────────────────

    def nfs_mount(self, host: str, path: str, mountpoint: str) -> dict:
        os.makedirs(mountpoint, exist_ok=True)
        return self.run_cmd(f"mount -t nfs {host}:{path} {mountpoint}")

    def nfs_unmount(self, mountpoint: str) -> dict:
        return self.run_cmd(f"umount {mountpoint}")

    def nfs_list_mounts(self) -> List[dict]:
        r = self.run_cmd("mount -t nfs,nfs4 -o noheadless | cat")
        mounts = []
        for line in r["stdout"].splitlines():
            if "nfs" in line.lower():
                parts = line.split()
                if len(parts) >= 3:
                    mounts.append({
                        "device": parts[0],
                        "mountpoint": parts[2],
                        "options": parts[4] if len(parts) > 4 else "",
                    })
        return mounts

    # ──────────────────────────────────────────────
    # CIFS/SMB
    # ──────────────────────────────────────────────

    def cifs_mount(self, host: str, share: str, mountpoint: str, username: str = "", password: str = "") -> dict:
        os.makedirs(mountpoint, exist_ok=True)
        opts = ""
        if username:
            opts = f"-o username={username},password={password}"
        return self.run_cmd(f"mount -t cifs //{host}/{share} {mountpoint} {opts}")

    def cifs_unmount(self, mountpoint: str) -> dict:
        return self.run_cmd(f"umount {mountpoint}")

    # ──────────────────────────────────────────────
    # Disk info
    # ──────────────────────────────────────────────

    def list_disks(self) -> List[dict]:
        r = self.run_cmd("lsblk -J -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL")
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            disks = []
            for dev in data.get("blockdevices", []):
                disks.append({
                    "name": dev.get("name"),
                    "size": dev.get("size"),
                    "type": dev.get("type"),
                    "fstype": dev.get("fstype"),
                    "mountpoint": dev.get("mountpoint"),
                    "model": dev.get("model"),
                    "children": [
                        {
                            "name": c.get("name"),
                            "size": c.get("size"),
                            "type": c.get("type"),
                            "fstype": c.get("fstype"),
                            "mountpoint": c.get("mountpoint"),
                        }
                        for c in dev.get("children", [])
                    ],
                })
            return disks
        except json.JSONDecodeError:
            return []

    def disk_health(self, device: str) -> dict:
        r = self.run_cmd(f"smartctl -H -j /dev/{device}")
        if not r["success"]:
            return {"device": device, "smart_available": False}
        try:
            data = json.loads(r["stdout"])
            return {
                "device": device,
                "smart_available": data.get("smart_status", {}).get("passed", None),
                "temperature": data.get("temperature", {}).get("current"),
            }
        except json.JSONDecodeError:
            return {"device": device, "smart_available": False}

    # ──────────────────────────────────────────────
    # Overview
    # ──────────────────────────────────────────────

    def get_storage_overview(self) -> dict:
        disks = self.list_disks()
        zfs_pools = self.zfs_list_pools()
        vgs = self.lvm_list_vgs()
        nfs = self.nfs_list_mounts()
        return {
            "disks": disks,
            "zfs_pools": zfs_pools,
            "lvm_groups": vgs,
            "nfs_mounts": nfs,
        }
