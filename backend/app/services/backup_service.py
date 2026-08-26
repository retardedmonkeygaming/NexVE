import subprocess
import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import List


class BackupService:
    BACKUP_DIR = "/var/lib/nexve/backups"

    def __init__(self):
        os.makedirs(self.BACKUP_DIR, exist_ok=True)

    def run_cmd(self, cmd: str, timeout: int = 300) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Timeout"}

    # ── VM Snapshots (via libvirt) ──

    def vm_snapshots(self, vm_id: int) -> List[dict]:
        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            if not conn:
                return []
            dom = conn.lookupByID(vm_id)
            if not dom:
                return []
            snaps = []
            for snap in dom.snapshotListXML(0).snapshots:
                info = {
                    "name": snap.name,
                    "description": snap.description or "",
                    "creation_time": datetime.fromtimestamp(snap.creationTime).isoformat() if snap.creationTime else "",
                }
                snaps.append(info)
            conn.close()
            return snaps
        except Exception as e:
            return [{"error": str(e)}]

    def vm_snapshot_create(self, vm_id: int, name: str, description: str = "") -> dict:
        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            if not conn:
                return {"success": False, "error": "Cannot connect to libvirt"}
            dom = conn.lookupByID(vm_id)
            if not dom:
                return {"success": False, "error": "VM not found"}
            flags = libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC
            xml = f"<domainsnapshot><name>{name}</name><description>{description}</description></domainsnapshot>"
            dom.snapshotCreateXML(xml, flags)
            conn.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vm_snapshot_delete(self, vm_id: int, name: str) -> dict:
        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            if not conn:
                return {"success": False, "error": "Cannot connect to libvirt"}
            dom = conn.lookupByID(vm_id)
            if not dom:
                return {"success": False, "error": "VM not found"}
            snap = dom.snapshotLookupByName(name, 0)
            snap.delete(0)
            conn.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vm_snapshot_restore(self, vm_id: int, name: str) -> dict:
        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            if not conn:
                return {"success": False, "error": "Cannot connect to libvirt"}
            dom = conn.lookupByID(vm_id)
            if not dom:
                return {"success": False, "error": "VM not found"}
            snap = dom.snapshotLookupByName(name, 0)
            flags = libvirt.VIR_DOMAIN_REVERT_TO_SNAPSHOT_RUNNING
            snap.revert(flags)
            conn.close()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── LXC Container Snapshots ──

    def container_snapshot_create(self, ct_id: int, name: str) -> dict:
        return self.run_cmd(f"pct snapshot {ct_id} {name}")

    def container_snapshots(self, ct_id: int) -> List[dict]:
        r = self.run_cmd(f"pct listsnapshot {ct_id}")
        if not r["success"]:
            return []
        snaps = []
        for line in r["stdout"].splitlines():
            parts = line.strip().split()
            if parts:
                snaps.append({"name": parts[0], "parent": parts[1] if len(parts) > 1 else ""})
        return snaps

    def container_snapshot_delete(self, ct_id: int, name: str) -> dict:
        return self.run_cmd(f"pct delsnapshot {ct_id} {name}")

    def container_snapshot_restore(self, ct_id: int, name: str) -> dict:
        return self.run_cmd(f"pct rollback {ct_id} {name}")

    # ── Full Backup / Restore ──

    def backup_vm(self, vm_id: int, compress: bool = True) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.BACKUP_DIR, f"vm_{vm_id}_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)

        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            if not conn:
                return {"success": False, "error": "Cannot connect to libvirt"}
            dom = conn.lookupByID(vm_id)
            if not dom:
                return {"success": False, "error": "VM not found"}

            # Dump VM XML config
            xml = dom.XMLDesc(0)
            with open(os.path.join(backup_path, "config.xml"), "w") as f:
                f.write(xml)

            # Get disk paths and copy them
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
            disk_index = 0
            for disk in root.findall(".//disk"):
                source = disk.find("source")
                if source is not None:
                    src_file = source.get("file", "")
                    if src_file and os.path.exists(src_file):
                        dest = os.path.join(backup_path, f"disk_{disk_index}.img")
                        shutil.copy2(src_file, dest)
                        disk_index += 1

            conn.close()

            # Compress if requested
            if compress:
                archive = f"{backup_path}.tar.gz"
                self.run_cmd(f"tar -czf {archive} -C {self.BACKUP_DIR} {os.path.basename(backup_path)}")
                shutil.rmtree(backup_path)
                return {"success": True, "path": archive, "size": os.path.getsize(archive)}

            return {"success": True, "path": backup_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def backup_container(self, ct_id: int) -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.BACKUP_DIR, f"ct_{ct_id}_{timestamp}.tar.gz")
        return self.run_cmd(f"vzdump {ct_id} --compress gzip --dumpdir {self.BACKUP_DIR}")

    # ── Incremental Backup ──

    def backup_vm_incremental(self, vm_id: int, base_snapshot: str = "") -> dict:
        """Create an incremental backup using qemu-img create with backing file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"vm_{vm_id}_incr_{timestamp}"
        backup_path = os.path.join(self.BACKUP_DIR, backup_name)
        os.makedirs(backup_path, exist_ok=True)

        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            if not conn:
                return {"success": False, "error": "Cannot connect to libvirt"}
            dom = conn.lookupByID(vm_id)
            if not dom:
                return {"success": False, "error": "VM not found"}

            xml = dom.XMLDesc(0)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)

            # Save config
            with open(os.path.join(backup_path, "config.xml"), "w") as f:
                f.write(xml)

            for disk in root.findall(".//disk"):
                source = disk.find("source")
                if source is not None:
                    src_file = source.get("file", "")
                    if src_file and os.path.exists(src_file):
                        dest = os.path.join(backup_path, os.path.basename(src_file))

                        if base_snapshot and os.path.exists(base_snapshot):
                            # Create an incremental qcow2 with backing file
                            r = self.run_cmd(
                                f'qemu-img create -f qcow2 -b {base_snapshot} -F qcow2 "{dest}"',
                            )
                            if not r["success"]:
                                return {"success": False, "error": r["stderr"]}

                            # Commit the diff
                            self.run_cmd(f'qemu-img commit -b "{base_snapshot}" "{dest}"')
                        else:
                            # No base: create a temporary snapshot for next incremental
                            snapshot_path = f"{dest}.base"
                            self.run_cmd(f'qemu-img snapshot -c nexve_base_{vm_id} "{src_file}"')
                            shutil.copy2(src_file, dest)

            # Save the latest disk as the base for next incremental
            for disk in root.findall(".//disk"):
                source = disk.find("source")
                if source is not None:
                    src_file = source.get("file", "")
                    if src_file and os.path.exists(src_file):
                        base_dir = os.path.join(self.BACKUP_DIR, f"vm_{vm_id}_base")
                        os.makedirs(base_dir, exist_ok=True)
                        base_path = os.path.join(base_dir, os.path.basename(src_file))
                        # Create a snapshot for next incremental
                        self.run_cmd(f'qemu-img snapshot -c incr_base_{vm_id} "{src_file}"')
                        shutil.copy2(src_file, base_path)

            conn.close()

            # Compress
            archive = f"{backup_path}.tar.gz"
            self.run_cmd(f"tar -czf {archive} -C {self.BACKUP_DIR} {backup_name}")
            shutil.rmtree(backup_path)

            return {
                "success": True,
                "path": archive,
                "size": os.path.getsize(archive) if os.path.exists(archive) else 0,
                "type": "incremental",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Backup Verification ──

    def verify_backup(self, backup_path: str) -> dict:
        """Verify a backup file is intact and readable."""
        if not os.path.exists(backup_path):
            return {"success": False, "error": "Backup file not found"}

        result = {"success": True, "checks": []}

        # Check if it's an archive
        if backup_path.endswith(".tar.gz"):
            r = self.run_cmd(f'tar -tzf "{backup_path}" > /dev/null')
            result["checks"].append({
                "name": "archive_integrity",
                "passed": r["success"],
                "detail": "Archive is readable" if r["success"] else r["stderr"],
            })

            if r["success"]:
                # List contents
                r2 = self.run_cmd(f'tar -tzf "{backup_path}"')
                result["checks"].append({
                    "name": "archive_contents",
                    "passed": r2["success"],
                    "detail": f"{len(r2['stdout'].splitlines())} files in archive",
                })
        elif backup_path.endswith(".qcow2"):
            # Verify qcow2 image
            r = self.run_cmd(f'qemu-img info "{backup_path}" --output=json')
            if r["success"]:
                try:
                    info = json.loads(r["stdout"])
                    result["checks"].append({
                        "name": "qcow2_info",
                        "passed": True,
                        "detail": f"Format: {info.get('format', 'unknown')}, Size: {info.get('virtual-size', 0) // (1024**3)}GB",
                    })
                except json.JSONDecodeError:
                    result["checks"].append({"name": "qcow2_info", "passed": False, "detail": "Cannot parse qemu-img info"})
            else:
                result["checks"].append({"name": "qcow2_info", "passed": False, "detail": r["stderr"]})

            # Check for corruption
            r2 = self.run_cmd(f'qemu-img check "{backup_path}"')
            result["checks"].append({
                "name": "qcow2_check",
                "passed": r2["success"],
                "detail": "No errors" if r2["success"] else r2["stderr"],
            })

        # Overall
        result["success"] = all(c["passed"] for c in result["checks"])
        return result

    def list_backups(self) -> List[dict]:
        backups = []
        if not os.path.exists(self.BACKUP_DIR):
            return backups
        for f in sorted(os.listdir(self.BACKUP_DIR), reverse=True):
            path = os.path.join(self.BACKUP_DIR, f)
            if os.path.isfile(path):
                stat = os.stat(path)
                backups.append({
                    "filename": f,
                    "path": path,
                    "size_bytes": stat.st_size,
                    "size_human": self._human_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": "vm" if f.startswith("vm_") else "container" if f.startswith("ct_") else "unknown",
                    "incremental": "incr" in f,
                })
        return backups

    def delete_backup(self, filename: str) -> dict:
        path = os.path.join(self.BACKUP_DIR, filename)
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"success": True}
        return {"success": False, "error": "Not found"}

    def _human_size(self, size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
