import subprocess
import os
import json
from typing import List, Optional, Dict
from datetime import datetime


class StorageService:
    """Manages local and remote storage backends via CLI commands."""

    def run_cmd(self, cmd: str, timeout: int = 10) -> dict:
        """Run a shell command with safe error handling."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out"}
        except Exception:
            return {"success": False, "stdout": "", "stderr": "Command not available"}

    # ──────────────────────────────────────────────
    # ZFS
    # ──────────────────────────────────────────────

    def _ensure_zfs_loaded(self) -> dict:
        """Check if ZFS kernel module is loaded; try to load it if not."""
        # Check if zfs module is loaded
        check = self.run_cmd("lsmod | grep -q zfs && echo loaded || echo missing")
        if check["stdout"].strip() == "loaded":
            return {"success": True}
        
        # Try to load the module
        load = self.run_cmd("modprobe zfs 2>&1")
        if load["success"]:
            return {"success": True}
        
        # Try alternative: check if zfs tools exist
        tools_check = self.run_cmd("which zpool 2>/dev/null")
        if not tools_check["success"]:
            return {
                "success": False,
                "error": "ZFS tools not installed.",
                "hint": "Install ZFS: apt install zfsutils-linux\nOn Proxmox: apt install zfsutils-linux"
            }
        
        return {
            "success": False,
            "error": f"ZFS kernel module cannot be loaded: {load.get('stderr', 'unknown error')}",
            "hint": "Try running: modprobe zfs\nIf that fails, ensure ZFS kernel modules are installed:\n  apt install zfsutils-linux linux-headers-$(uname -r)\nThen reboot."
        }

    def zfs_status(self) -> dict:
        """Get ZFS system status."""
        loaded = self.run_cmd("lsmod | grep -q zfs && echo loaded || echo missing")
        tools = self.run_cmd("which zpool 2>/dev/null && echo available || echo missing")
        pools = self.zfs_list_pools()
        return {
            "module_loaded": loaded["stdout"].strip() == "loaded",
            "tools_available": tools["stdout"].strip() == "available",
            "pool_count": len(pools),
            "pools": pools,
        }


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

    def zfs_create_pool(self, name: str, device: str, force: bool = False,
                        pool_type: str = "single", devices: List[str] = None) -> dict:
        """Create a ZFS pool with single or multiple devices.
        pool_type: single, mirror, raidz, raidz2, raidz3, stripe
        """
        check = self._ensure_zfs_loaded()
        if not check["success"]:
            return check
        force_flag = "-f" if force else ""
        devs = devices or [d.strip() for d in device.split() if d.strip()]
        if len(devs) == 0:
            return {"success": False, "error": "No devices specified"}
        if pool_type == "single" or len(devs) == 1:
            dev_str = " ".join(devs)
            return self.run_cmd(f"zpool create {force_flag} {name} {dev_str}")
        elif pool_type == "mirror":
            dev_str = " ".join(devs)
            return self.run_cmd(f"zpool create {force_flag} {name} mirror {dev_str}")
        elif pool_type in ("raidz", "raidz2", "raidz3"):
            dev_str = " ".join(devs)
            return self.run_cmd(f"zpool create {force_flag} {name} {pool_type} {dev_str}")
        elif pool_type == "stripe":
            dev_str = " ".join(devs)
            return self.run_cmd(f"zpool create {force_flag} {name} stripe {dev_str}")
        else:
            dev_str = " ".join(devs)
            return self.run_cmd(f"zpool create {force_flag} {name} {dev_str}")

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
        check = self._ensure_zfs_loaded()
        if not check["success"]:
            return check
        return self.run_cmd(f"zfs create -V {size_gb}G {pool}/{name}")

    def zfs_create_dataset(self, pool: str, name: str) -> dict:
        check = self._ensure_zfs_loaded()
        if not check["success"]:
            return check
        return self.run_cmd(f"zfs create {pool}/{name}")

    def zfs_destroy(self, volume: str) -> dict:
        return self.run_cmd(f"zfs destroy -rf {volume}")

    def zfs_snapshots(self, volume: str) -> List[dict]:
        r = self.run_cmd(f"zfs list -t snapshot -H -o name,used,refer,creation -J {volume}")
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def zfs_snapshot(self, volume: str, snap_name: str) -> dict:
        return self.run_cmd(f"zfs snapshot {volume}@{snap_name}")

    def zfs_scrub(self, pool: str) -> dict:
        return self.run_cmd(f"zpool scrub {pool}")

    def zfs_rename(self, volume: str, new_name: str) -> dict:
        return self.run_cmd(f"zfs rename {volume} {new_name}")

    # ── ZFS Replication ──

    def zfs_replicate(self, source: str, target: str, snapshot: str = "") -> dict:
        """Replicate a ZFS dataset to a target. If no snapshot given, create a fresh one."""
        if not snapshot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot = f"{source}@repl_{timestamp}"
            r = self.run_cmd(f"zfs snapshot {snapshot}")
            if not r["success"]:
                return r

        r = self.run_cmd(
            f"zfs send {snapshot} | zfs receive -F {target}",
            timeout=300,
        )
        return {
            "success": r["success"],
            "snapshot": snapshot,
            "stdout": r["stdout"],
            "stderr": r["stderr"],
        }

    def zfs_replication_status(self) -> List[dict]:
        """List recent ZFS send/receive operations from history."""
        r = self.run_cmd("zfs history -l 2>/dev/null | tail -50")
        jobs = []
        if r["success"]:
            for line in r["stdout"].splitlines():
                if "send" in line or "receive" in line:
                    jobs.append({"info": line.strip()})
        return jobs

    # ── ZFS Quotas ──

    def zfs_set_quota(self, volume: str, size_gb: int) -> dict:
        return self.run_cmd(f"zfs set quota={size_gb}G {volume}")

    def zfs_get_quota(self, volume: str) -> dict:
        r = self.run_cmd(f"zfs get quota -H -o value {volume}")
        return {"quota": r["stdout"] if r["success"] else "none"}

    # ──────────────────────────────────────────────
    # BTRFS
    # ──────────────────────────────────────────────

    def btrfs_list_pools(self) -> List[dict]:
        r = self.run_cmd("btrfs filesystem show --raw -J 2>/dev/null")
        if not r["success"]:
            # Fallback: parse text output
            r2 = self.run_cmd("mount -t btrfs | awk '{print $3}'")
            pools = []
            if r2["success"]:
                for line in r2["stdout"].splitlines():
                    if line.strip():
                        pools.append({"path": line.strip(), "type": "btrfs"})
            return pools
        try:
            data = json.loads(r["stdout"])
            return data.get("filesystems", [])
        except json.JSONDecodeError:
            return []

    def btrfs_list_subvolumes(self, pool: str) -> List[dict]:
        r = self.run_cmd(f"btrfs subvolume list -p {pool}")
        subvols = []
        if r["success"]:
            for line in r["stdout"].splitlines():
                parts = line.split()
                if len(parts) >= 9:
                    subvols.append({
                        "id": parts[1],
                        "path": parts[-1] if "path" not in parts[8] else " ".join(parts[8:]),
                        "parent": parts[3].rstrip(","),
                    })
        return subvols

    def btrfs_create_subvolume(self, pool: str, name: str) -> dict:
        return self.run_cmd(f"btrfs subvolume create {pool}/{name}")

    def btrfs_delete_subvolume(self, path: str) -> dict:
        return self.run_cmd(f"btrfs subvolume delete {path}")

    def btrfs_snapshot(self, source: str, dest: str) -> dict:
        return self.run_cmd(f"btrfs subvolume snapshot {source} {dest}")

    def btrfs_balance(self, pool: str) -> dict:
        return self.run_cmd(f"btrfs balance start {pool}", timeout=120)

    def btrfs_usage(self, pool: str) -> dict:
        r = self.run_cmd(f"btrfs filesystem usage -b {pool}")
        if not r["success"]:
            return {}
        # Parse basic usage
        result = {}
        for line in r["stdout"].splitlines():
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                result[k.strip()] = v.strip()
        return result

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

    def lvm_resize_lv(self, lv_path: str, size_gb: int) -> dict:
        """Resize a logical volume (LV) to the specified size in GB."""
        if not lv_path.startswith("/"):
            # Might be just "vg/lv" format
            pass
        return self.run_cmd(f"lvresize -L {size_gb}G -r {lv_path}")

    # ──────────────────────────────────────────────
    # Directory-based storage
    # ──────────────────────────────────────────────


    # ── LVM-thin provisioning ──

    def lvm_thin_create_pool(self, vg_name: str, pool_name: str, size_gb: int) -> dict:
        """Create a thin pool in a volume group."""
        # Create the data and metadata LVs for the thin pool
        data_lv = f"{pool_name}_data"
        meta_lv = f"{pool_name}_meta"
        meta_size = max(64, size_gb // 20)  # ~5% for metadata

        # Create data LV
        r1 = self.run_cmd(f"lvcreate -L {size_gb}G -T {vg_name}/{data_lv}")
        if not r1["success"]:
            return r1

        # Create metadata LV
        r2 = self.run_cmd(f"lvcreate -L {meta_size}G -T {vg_name}/{meta_lv}")
        if not r2["success"]:
            return r2

        # Convert data LV to a thin pool with the metadata
        return self.run_cmd(f"lvconvert --type thin-pool --poolmetadata {vg_name}/{meta_lv} {vg_name}/{data_lv}")

    def lvm_thin_create_lv(self, vg_name: str, pool_name: str, lv_name: str, size_gb: int) -> dict:
        """Create a thin volume in a thin pool."""
        return self.run_cmd(f"lvcreate -V {size_gb}G -T {vg_name}/{pool_name} -n {lv_name}")

    def lvm_thin_list_pools(self, vg_name: str = "") -> List[dict]:
        """List thin pools."""
        cmd = "lvs --type thin_pool --reportformat json"
        if vg_name:
            cmd += f" {vg_name}"
        r = self.run_cmd(cmd)
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            pools = data.get("report", [{}])[0].get("lv", [])
            return [
                {
                    "name": lv.get("lv_name"),
                    "vg": lv.get("vg_name"),
                    "size": lv.get("lv_size"),
                    "data_percent": lv.get("data_percent", "0"),
                    "metadata_percent": lv.get("metadata_percent", "0"),
                }
                for lv in pools
            ]
        except (json.JSONDecodeError, IndexError):
            return []

    def lvm_thin_list_volumes(self, vg_name: str = "", pool_name: str = "") -> List[dict]:
        """List thin volumes."""
        cmd = "lvs --type thin --reportformat json"
        if vg_name:
            cmd += f" {vg_name}"
        r = self.run_cmd(cmd)
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            vols = data.get("report", [{}])[0].get("lv", [])
            result = []
            for lv in vols:
                if pool_name and lv.get("pool_lv", "") != pool_name:
                    continue
                result.append({
                    "name": lv.get("lv_name"),
                    "vg": lv.get("vg_name"),
                    "pool": lv.get("pool_lv", ""),
                    "size": lv.get("lv_size"),
                    "origin": lv.get("origin", ""),
                })
            return result
        except (json.JSONDecodeError, IndexError):
            return []

    def lvm_thin_remove_pool(self, vg_name: str, pool_name: str) -> dict:
        """Remove a thin pool and its volumes."""
        return self.run_cmd(f"lvremove -f {vg_name}/{pool_name}")

    def lvm_thin_remove_lv(self, lv_path: str) -> dict:
        """Remove a thin volume."""
        return self.run_cmd(f"lvremove -f {lv_path}")

    def lvm_thin_snapshot(self, source_lv: str, snap_name: str) -> dict:
        """Create a thin snapshot of a thin volume."""
        return self.run_cmd(f"lvcreate -s -n {snap_name} {source_lv}")

    def lvm_thin_list_snapshots(self, vg_name: str = "") -> List[dict]:
        """List LVM snapshots."""
        cmd = "lvs --type snapshot --reportformat json"
        if vg_name:
            cmd += f" {vg_name}"
        r = self.run_cmd(cmd)
        if not r["success"]:
            return []
        try:
            data = json.loads(r["stdout"])
            snaps = data.get("report", [{}])[0].get("lv", [])
            return [
                {
                    "name": lv.get("lv_name"),
                    "vg": lv.get("vg_name"),
                    "origin": lv.get("origin", ""),
                    "size": lv.get("lv_size"),
                    "percent": lv.get("data_percent", "0"),
                }
                for lv in snaps
            ]
        except (json.JSONDecodeError, IndexError):
            return []

    def lvm_thin_resize(self, lv_path: str, size_gb: int) -> dict:
        """Resize a thin volume (logical size, not actual allocation)."""
        return self.run_cmd(f"lvresize -V {size_gb}G -r {lv_path}")

    def lvm_thin_pool_usage(self, vg_name: str, pool_name: str) -> dict:
        """Get thin pool usage details."""
        r = self.run_cmd(f"lvs -o lv_name,data_percent,metadata_percent,lv_size --noheadings --reportformat json {vg_name}/{pool_name}")
        if not r["success"]:
            return {}
        try:
            data = json.loads(r["stdout"])
            lv = data.get("report", [{}])[0].get("lv", [{}])[0]
            return {
                "name": lv.get("lv_name"),
                "data_percent": lv.get("data_percent", "0"),
                "metadata_percent": lv.get("metadata_percent", "0"),
                "total_size": lv.get("lv_size", "0"),
            }
        except (json.JSONDecodeError, IndexError):
            return {}

    # ── Storage Migration ──

    def migrate_storage(self, source_storage: str, target_storage: str, vm_id: int = 0) -> dict:
        """Migrate all volumes/images from one storage backend to another."""
        source_path = self._get_storage_path(source_storage)
        target_path = self._get_storage_path(target_storage)

        if not source_path or not target_path:
            return {"success": False, "error": "Invalid storage backends"}

        try:
            import shutil
            import os

            if not os.path.isdir(source_path):
                return {"success": False, "error": f"Source path not found: {source_path}"}

            os.makedirs(target_path, exist_ok=True)

            migrated = []
            errors = []

            for item in os.listdir(source_path):
                src = os.path.join(source_path, item)
                dst = os.path.join(target_path, item)

                if os.path.isfile(src):
                    try:
                        shutil.copy2(src, dst)
                        migrated.append(item)
                    except Exception as e:
                        errors.append({"file": item, "error": str(e)})

            return {
                "success": len(errors) == 0,
                "migrated": migrated,
                "errors": errors,
                "source": source_storage,
                "target": target_storage,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

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
        r = self.run_cmd("mount | grep nfs", timeout=5)
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

    def disk_info(self, device: str) -> dict:
        """Get detailed disk info via lsblk."""
        r = self.run_cmd(f"lsblk -J -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL,REV /dev/{device}")
        if not r["success"]:
            return {}
        try:
            data = json.loads(r["stdout"])
            devs = data.get("blockdevices", [])
            return devs[0] if devs else {}
        except json.JSONDecodeError:
            return {}

    # ──────────────────────────────────────────────
    # Overview
    # ──────────────────────────────────────────────

    def get_storage_overview(self) -> dict:
        """Get storage overview with individual error handling."""
        try:
            disks = self.list_disks()
        except Exception:
            disks = []
        try:
            zfs_pools = self.zfs_list_pools()
        except Exception:
            zfs_pools = []
        try:
            vgs = self.lvm_list_vgs()
        except Exception:
            vgs = []
        try:
            nfs = self.nfs_list_mounts()
        except Exception:
            nfs = []
        try:
            btrfs = self.btrfs_list_pools()
        except Exception:
            btrfs = []
        try:
            local_usage = self.dir_usage("/")
        except Exception:
            local_usage = None
        return {
            "disks": disks,
            "zfs_pools": zfs_pools,
            "lvm_groups": vgs,
            "nfs_mounts": nfs,
            "btrfs_pools": btrfs,
            "local_usage": local_usage,
        }

    # ──────────────────────────────────────────────
    # Disk operations
    # ──────────────────────────────────────────────

    def wipe_disk(self, device: str) -> dict:
        return self.run_cmd(f"wipefs -a {device}")

    def move_disk(self, vm_name: str, source: str, target: str) -> dict:
        """Move a VM disk between storage backends."""
        # In a real setup this would use virsh or qemu-img to copy the disk.
        return {
            "success": False,
            "error": "Disk move requires VM to be stopped. Use the migration API endpoint for proper disk migration.",
        }

    def migrate_disk(self, vm_name: str, disk_index: int, target_storage: str) -> dict:
        """Migrate a VM disk to a different storage backend."""
        try:
            import shutil
            import libvirt

            conn = libvirt.open("qemu:///system")
            if not conn:
                return {"success": False, "error": "Cannot connect to libvirt"}

            dom = conn.lookupByName(vm_name)
            if not dom:
                return {"success": False, "error": "VM not found in libvirt"}

            # Get disk info from XML
            import xml.etree.ElementTree as ET
            xml = dom.XMLDesc(0)
            root = ET.fromstring(xml)
            disks = root.findall(".//disk")
            if disk_index >= len(disks):
                return {"success": False, "error": f"No disk at index {disk_index}"}

            disk = disks[disk_index]
            source = disk.find("source")
            if source is None:
                return {"success": False, "error": "No disk source found"}

            src_file = source.get("file", "")
            if not src_file or not os.path.exists(src_file):
                return {"success": False, "error": f"Source file not found: {src_file}"}

            # Determine target path
            target_dir = self._get_storage_path(target_storage)
            if not target_dir:
                return {"success": False, "error": f"Unknown target storage: {target_storage}"}

            dst_file = os.path.join(target_dir, os.path.basename(src_file))

            # Copy the disk
            shutil.copy2(src_file, dst_file)

            # Update libvirt XML
            source.set("file", dst_file)
            new_xml = ET.tostring(root, encoding="unicode")
            dom.undefine()
            conn.defineXML(new_xml)

            # Remove old file
            os.remove(src_file)

            conn.close()
            return {"success": True, "new_path": dst_file}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_storage_path(self, storage_name: str) -> str:
        """Get filesystem path for a named storage backend."""
        storage_paths = {
            "local": "/var/lib/libvirt/images",
            "local-lvm": "/dev",
            "backups": "/opt/nexve/data/backups",
        }
        if storage_name in storage_paths:
            return storage_paths[storage_name]
        # Check database
        try:
            from ..database import SessionLocal
            from ..models.storage import Storage
            db = SessionLocal()
            try:
                s = db.query(Storage).filter(Storage.name == storage_name).first()
                if s and s.path:
                    return s.path
            finally:
                db.close()
        except Exception:
            pass
        return "/var/lib/libvirt/images"

    # ──────────────────────────────────────────────
    # Storage Quotas
    # ──────────────────────────────────────────────

    def list_quotas(self) -> List[dict]:
        """List filesystem quotas using quota or xfs quota tools."""
        r = self.run_cmd("repquota -a 2>/dev/null || echo ''")
        quotas = []
        if r["success"] and r["stdout"]:
            for line in r["stdout"].splitlines():
                # Basic parsing of repquota output
                if line.startswith("/") and "blocks" not in line.lower():
                    parts = line.split()
                    if len(parts) >= 2:
                        quotas.append({
                            "path": parts[0],
                            "user": parts[1] if len(parts) > 1 else "",
                        })
        return quotas

    def set_quota(self, path: str, size_gb: int) -> dict:
        """Set a quota on a filesystem using xfs_quota or edquota."""
        # For ext4: use quota
        # For XFS: use xfs_quota
        r = self.run_cmd(f"xfs_quota -x -c 'limit bsoft={size_gb}g bhard={size_gb}g' {path}")
        if not r["success"]:
            # Fallback: try edquota-style
            r = self.run_cmd(f"setquota -g 0 {size_gb}G 0 0 {path}")
        return {"success": r["success"], "stderr": r["stderr"]}

    # ── GlusterFS ──

    def _has_gluster(self) -> bool:
        r = self.run_cmd("which gluster 2>/dev/null")
        return r["success"]

    def gluster_status(self) -> dict:
        if not self._has_gluster():
            return {"available": False}
        r = self.run_cmd("gluster peer status 2>&1")
        peers = []
        in_peer = False
        for line in r["stdout"].splitlines():
            if "Hostname" in line:
                peers.append({"hostname": line.split(":")[-1].strip()})
                in_peer = True
            elif in_peer and "State" in line:
                peers[-1]["state"] = line.split(":")[-1].strip()
                in_peer = False
        return {"available": True, "peers": peers, "raw": r["stdout"]}

    def gluster_list_volumes(self) -> List[dict]:
        r = self.run_cmd("gluster volume list 2>&1")
        volumes = []
        for line in r["stdout"].splitlines():
            v = line.strip()
            if v and not v.startswith("Volume") and "No volumes" not in v:
                # Get volume info
                info = self.run_cmd(f"gluster volume info {v} 2>&1")
                details = {}
                for il in info["stdout"].splitlines():
                    if ":" in il:
                        k, val = il.split(":", 1)
                        details[k.strip().lower().replace(" ", "_")] = val.strip()
                volumes.append({"name": v, "status": details.get("status", "unknown"),
                               "type": details.get("type", "unknown"),
                               "bricks": details.get("number_of_bricks", "0")})
        return volumes

    def gluster_create_volume(self, name: str, bricks: List[str],
                             replica_count: int = 1, transport: str = "tcp") -> dict:
        bricks_str = " ".join(bricks)
        cmd = f"gluster volume create {name}"
        if replica_count > 1:
            cmd += f" replica {replica_count}"
        cmd += f" transport {transport} {bricks_str} force 2>&1"
        r = self.run_cmd(cmd, timeout=60)
        if r["success"]:
            self.run_cmd(f"gluster volume start {name} 2>&1")
        return {"success": r["success"], "output": r["stdout"], "error": r["stderr"]}

    def gluster_delete_volume(self, name: str) -> dict:
        self.run_cmd(f"gluster volume stop {name} force 2>&1", timeout=30)
        r = self.run_cmd(f"gluster volume delete {name} 2>&1", timeout=30)
        return {"success": r["success"], "error": r["stderr"]}

    def gluster_peer_probe(self, host: str) -> dict:
        r = self.run_cmd(f"gluster peer probe {host} 2>&1", timeout=15)
        return {"success": r["success"], "output": r["stdout"], "error": r["stderr"]}

    def gluster_peer_detach(self, host: str) -> dict:
        r = self.run_cmd(f"gluster peer detach {host} force 2>&1", timeout=15)
        return {"success": r["success"], "error": r["stderr"]}

    def gluster_volume_info(self, name: str) -> dict:
        r = self.run_cmd(f"gluster volume info {name} 2>&1")
        info = {}
        for line in r["stdout"].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                info[k.strip().lower().replace(" ", "_")] = v.strip()
        return info

    # ── RAIDZ Expansion ──

    def zfs_raidz_expand(self, pool: str, new_device: str) -> dict:
        """Expand a RAIDZ pool by adding a new device."""
        r = self.run_cmd(f"zpool attach {pool} {new_device} 2>&1", timeout=300)
        if r["success"]:
            return {"success": True, "message": f"Device {new_device} added to pool {pool}. Resilver in progress."}
        # Try add for RAIDZ vdev expansion
        r2 = self.run_cmd(f"zpool add {pool} {new_device} 2>&1", timeout=300)
        return {"success": r2["success"], "output": r2["stdout"], "error": r2["stderr"] or r["stderr"]}

    def zfs_raidz_status(self, pool: str) -> dict:
        """Get RAIDZ pool status (resilver progress, errors, etc.)."""
        r = self.run_cmd(f"zpool status {pool} 2>&1")
        return {"output": r["stdout"], "error": r["stderr"]}

    def zfs_raidz_add_vdev(self, pool: str, devices: List[str]) -> dict:
        """Add a new RAIDZ vdev to an existing pool."""
        devs = " ".join(devices)
        r = self.run_cmd(f"zpool add {pool} raidz {devs} 2>&1", timeout=600)
        return {"success": r["success"], "output": r["stdout"], "error": r["stderr"]}

    # ── Scheduled Replication Jobs ──

    REPLICATION_FILE = "/var/lib/nexve/replication.json"

    def _save_replication(self, jobs: List[dict]):
        import os
        os.makedirs(os.path.dirname(self.REPLICATION_FILE), exist_ok=True)
        with open(self.REPLICATION_FILE, "w") as f:
            json.dump(jobs, f, indent=2)

    def _load_replication(self) -> List[dict]:
        if os.path.exists(self.REPLICATION_FILE):
            with open(self.REPLICATION_FILE) as f:
                return json.load(f)
        return []

    def replication_list_jobs(self) -> List[dict]:
        return self._load_replication()

    def replication_create_job(self, source: str, target: str, schedule: str = "daily",
                              recursive: bool = True, max_snapshots: int = 10) -> dict:
        jobs = self._load_replication()
        job_id = len(jobs) + 1
        job = {
            "id": job_id, "source": source, "target": target,
            "schedule": schedule, "recursive": recursive,
            "max_snapshots": max_snapshots, "enabled": True,
            "last_run": None, "last_status": None,
        }
        jobs.append(job)
        self._save_replication(jobs)
        # Schedule via cron
        cron_line = self._schedule_to_cron(schedule)
        self.run_cmd(
            f"(crontab -l 2>/dev/null | grep -v 'nexve-repl-{job_id}'; "
            f"echo '{cron_line} /usr/sbin/zfs send -R {source} | zfs recv -F {target} # nexve-repl-{job_id}') | crontab -"
        )
        return {"success": True, "job": job}

    def replication_delete_job(self, job_id: int) -> dict:
        jobs = self._load_replication()
        jobs = [j for j in jobs if j["id"] != job_id]
        self._save_replication(jobs)
        self.run_cmd(f"crontab -l 2>/dev/null | grep -v 'nexve-repl-{job_id}' | crontab -")
        return {"success": True}

    def replication_run_now(self, job_id: int) -> dict:
        jobs = self._load_replication()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            return {"success": False, "error": "Job not found"}
        source = job["source"]
        target = job["target"]
        # Create snapshot first
        snap_name = f"repl-{int(time.time())}"
        self.zfs_snapshot(source, snap_name)
        # Send/receive
        cmd = f"zfs send -R {source}@{snap_name} | zfs recv -F {target} 2>&1"
        r = self.run_cmd(cmd, timeout=3600)
        # Update job status
        for j in jobs:
            if j["id"] == job_id:
                j["last_run"] = datetime.utcnow().isoformat()
                j["last_status"] = "success" if r["success"] else "failed"
        self._save_replication(jobs)
        return {"success": r["success"], "output": r["stdout"], "error": r["stderr"]}

    def _schedule_to_cron(self, schedule: str) -> str:
        schedules = {
            "hourly": "0 * * * *",
            "daily": "0 2 * * *",
            "weekly": "0 2 * * 0",
            "monthly": "0 2 1 * *",
            "every6h": "0 */6 * * *",
            "every12h": "0 */12 * * *",
        }
        return schedules.get(schedule, "0 2 * * *")
