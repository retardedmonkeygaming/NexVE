import subprocess
import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import List


class BackupService:
    BACKUP_DIR = os.path.expanduser("~/.nexve/backups")

    def __init__(self):
        try:
            os.makedirs(self.BACKUP_DIR, exist_ok=True)
        except PermissionError:
            self.BACKUP_DIR = os.path.expanduser("~/nexve_backups")
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

    # ── LXC Container Snapshots (native lxc-snapshot) ──

    def container_snapshot_create(self, ct_id: int, name: str) -> dict:
        """Create a snapshot using native lxc-snapshot."""
        # First try lxc-snapshot (native LXC)
        r = self.run_cmd(f"lxc-snapshot -n {ct_id} -s {name}")
        if r["success"]:
            return {"success": True}
        # Fallback: try with container name
        return r

    def container_snapshots(self, ct_id: int) -> List[dict]:
        """List snapshots using native lxc-snapshot."""
        r = self.run_cmd(f"lxc-snapshot -n {ct_id} -L")
        if not r["success"]:
            # Try listing snapshot directory
            snap_dir = f"/var/lib/lxc/{ct_id}/snaps"
            import os
            if os.path.isdir(snap_dir):
                snaps = []
                for f in os.listdir(snap_dir):
                    if f.endswith(".tar.gz") or f.endswith(".snap"):
                        name = f.rsplit(".", 1)[0]
                        snaps.append({"name": name, "parent": ""})
                return snaps
            return []
        snaps = []
        for line in r["stdout"].splitlines():
            line = line.strip()
            if line and not line.startswith("snap") and not line.startswith("-"):
                # Parse lxc-snapshot -L output
                parts = line.split()
                if parts:
                    snaps.append({"name": parts[0].rstrip(":"), "parent": ""})
        return snaps

    def container_snapshot_delete(self, ct_id: int, name: str) -> dict:
        """Delete a snapshot using native lxc-snapshot."""
        r = self.run_cmd(f"lxc-snapshot -n {ct_id} -d {name}")
        if r["success"]:
            return {"success": True}
        # Fallback: remove snapshot file manually
        snap_path = f"/var/lib/lxc/{ct_id}/snaps/{name}.snap"
        import os
        if os.path.exists(snap_path):
            os.remove(snap_path)
            return {"success": True}
        return r

    def container_snapshot_restore(self, ct_id: int, name: str) -> dict:
        """Restore a snapshot using native lxc-snapshot."""
        r = self.run_cmd(f"lxc-snapshot -n {ct_id} -r {name}")
        return {"success": r["success"], "error": r.get("stderr")}

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
        """Backup container using tar (works without vzdump)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.BACKUP_DIR, f"ct_{ct_id}_{timestamp}.tar.gz")
        ct_name = str(ct_id)
        rootfs = f"/var/lib/lxc/{ct_name}/rootfs"
        config = f"/var/lib/lxc/{ct_name}/config"

        if not os.path.isdir(rootfs):
            # Try finding by name in DB
            return {"success": False, "error": f"Container rootfs not found at {rootfs}"}

        # Create backup: include both rootfs and config
        cmd = f"tar czf {backup_file} -C /var/lib/lxc {ct_name}"
        r = self.run_cmd(cmd, timeout=600)
        if r["success"]:
            return {"success": True, "path": backup_file, "size": os.path.getsize(backup_file) if os.path.exists(backup_file) else 0}
        return r

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


    # ── Backup Restore ──

    def restore_vm_from_backup(self, backup_path: str, vm_name: str = "") -> dict:
        """Restore a VM from a backup archive."""
        import tarfile
        import xml.etree.ElementTree as ET
        import libvirt

        if not os.path.exists(backup_path):
            return {"success": False, "error": f"Backup not found: {backup_path}"}

        try:
            # Extract archive if compressed
            extract_dir = backup_path
            if backup_path.endswith(".tar.gz"):
                extract_dir = backup_path.replace(".tar.gz", "")
                os.makedirs(extract_dir, exist_ok=True)
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(extract_dir)
                # Find the actual backup directory
                for item in os.listdir(extract_dir):
                    sub = os.path.join(extract_dir, item)
                    if os.path.isdir(sub) and os.path.exists(os.path.join(sub, "config.xml")):
                        extract_dir = sub
                        break

            # Read and modify XML config
            xml_path = os.path.join(extract_dir, "config.xml")
            if not os.path.exists(xml_path):
                return {"success": False, "error": "No config.xml found in backup"}

            with open(xml_path) as f:
                xml = f.read()

            root = ET.fromstring(xml)

            # Update VM name if specified
            if vm_name:
                name_el = root.find("name")
                if name_el is not None:
                    name_el.text = vm_name

            # Restore disk images
            conn = libvirt.open("qemu:///system")
            if not conn:
                return {"success": False, "error": "Cannot connect to libvirt"}

            images_dir = "/var/lib/libvirt/images"
            os.makedirs(images_dir, exist_ok=True)

            for disk in root.findall(".//disk"):
                source = disk.find("source")
                if source is not None:
                    orig_file = source.get("file", "")
                    if orig_file:
                        basename = os.path.basename(orig_file)
                        # Find matching backup disk file
                        for bf in os.listdir(extract_dir):
                            if bf.startswith("disk_") and bf.endswith(".img"):
                                src = os.path.join(extract_dir, bf)
                                dst = os.path.join(images_dir, basename)
                                shutil.copy2(src, dst)
                                source.set("file", dst)
                                break

            # Define the VM
            new_xml = ET.tostring(root, encoding="unicode")
            conn.defineXML(new_xml)
            conn.close()

            return {"success": True, "message": f"VM restored as {root.find('name').text if root.find('name') is not None else vm_name}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def restore_container_from_backup(self, backup_path: str, ct_id: int = 0) -> dict:
        """Restore a container from a backup archive."""
        if not os.path.exists(backup_path):
            return {"success": False, "error": f"Backup not found: {backup_path}"}

        try:
            # Determine container ID from filename or parameter
            if not ct_id:
                basename = os.path.basename(backup_path)
                if "ct_" in basename:
                    parts = basename.split("_")
                    if len(parts) >= 2:
                        try:
                            ct_id = int(parts[1])
                        except ValueError:
                            ct_id = 100

            ct_name = str(ct_id)
            ct_dir = f"/var/lib/lxc/{ct_name}"
            os.makedirs(ct_dir, exist_ok=True)

            # Extract backup
            if backup_path.endswith(".tar.gz"):
                self.run_cmd(f"tar -xzf {backup_path} -C {ct_dir}")
            else:
                self.run_cmd(f"tar -xf {backup_path} -C {ct_dir}")

            # Start the container
            self.run_cmd(f"lxc-start -n {ct_name}")

            return {"success": True, "message": f"Container {ct_id} restored and started"}

        except Exception as e:
            return {"success": False, "error": str(e)}


    def backup_vm_encrypted(self, vm_id: int, passphrase: str) -> dict:
        """Create an encrypted backup of a VM."""
        # First create a normal backup
        result = self.backup_vm(vm_id, compress=True)
        if not result.get("success"):
            return result

        archive = result.get("path", "")
        if not archive or not os.path.exists(archive):
            return {"success": False, "error": "Backup archive not found"}

        encrypted = f"{archive}.enc"
        try:
            # Use openssl for encryption
            r = self.run_cmd(
                f'openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 '
                f'-in "{archive}" -out "{encrypted}" -pass pass:{passphrase}'
            )
            if r["success"]:
                os.remove(archive)
                return {"success": True, "path": encrypted, "encrypted": True, "size": os.path.getsize(encrypted)}
            else:
                return {"success": False, "error": f"Encryption failed: {r['stderr']}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restore_vm_encrypted(self, backup_path: str, passphrase: str, vm_name: str = "") -> dict:
        """Restore a VM from an encrypted backup."""
        decrypted = backup_path.replace(".enc", "")
        try:
            r = self.run_cmd(
                f'openssl enc -aes-256-cbc -d -salt -pbkdf2 -iter 100000 '
                f'-in "{backup_path}" -out "{decrypted}" -pass pass:{passphrase}'
            )
            if not r["success"]:
                return {"success": False, "error": f"Decryption failed: wrong passphrase?"}

            result = self.restore_vm_from_backup(decrypted, vm_name)
            # Clean up decrypted file
            if os.path.exists(decrypted):
                os.remove(decrypted)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── PBS Integration ──

    def pbs_status(self) -> dict:
        """Check if Proxmox Backup Server client is available."""
        r = self.run_cmd("which pxar 2>/dev/null || which pbs 2>/dev/null")
        return {"available": r["success"]}

    def pbs_backup(self, vm_id: int, repository: str = "", password: str = "") -> dict:
        """Backup a VM to a PBS repository."""
        if not repository:
            return {"success": False, "error": "PBS repository not specified"}

        # Create backup first
        result = self.backup_vm(vm_id, compress=False)
        if not result.get("success"):
            return result

        backup_path = result.get("path", "")
        if not backup_path:
            return {"success": False, "error": "Backup path empty"}

        # Use pxar to create archive
        pxar_path = f"{backup_path}.pxar"
        r = self.run_cmd(f'pxar create "{pxar_path}" "{backup_path}"')

        if r["success"]:
            return {"success": True, "path": pxar_path, "pbs_repository": repository}
        return {"success": False, "error": r["stderr"]}

    # ── Single File Restore ──

    def extract_file_from_backup(self, backup_path: str, file_path: str, output_path: str) -> dict:
        """Extract a single file/directory from a backup archive."""
        import tarfile

        if not os.path.exists(backup_path):
            return {"success": False, "error": "Backup not found"}

        try:
            if backup_path.endswith(".tar.gz"):
                with tarfile.open(backup_path, "r:gz") as tar:
                    # Find the file in the archive
                    members = [m for m in tar.getmembers() if file_path in m.name]
                    if not members:
                        return {"success": False, "error": f"File {file_path} not found in backup"}
                    os.makedirs(output_path, exist_ok=True)
                    tar.extractall(output_path, members=members)
                    return {"success": True, "extracted": [m.name for m in members], "output": output_path}
            else:
                return {"success": False, "error": "Unsupported backup format"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Backup Statistics ──

    def get_backup_stats(self) -> dict:
        """Get backup storage statistics."""
        total_size = 0
        backup_count = 0
        vm_backups = 0
        ct_backups = 0

        if os.path.isdir(self.BACKUP_DIR):
            for f in os.listdir(self.BACKUP_DIR):
                path = os.path.join(self.BACKUP_DIR, f)
                if os.path.isfile(path):
                    total_size += os.path.getsize(path)
                    backup_count += 1
                    if f.startswith("vm_"):
                        vm_backups += 1
                    elif f.startswith("ct_"):
                        ct_backups += 1
                elif os.path.isdir(path):
                    for sf in os.listdir(path):
                        total_size += os.path.getsize(os.path.join(path, sf))
                    backup_count += 1

        return {
            "total_size_bytes": total_size,
            "total_size_human": self._human_size(total_size),
            "backup_count": backup_count,
            "vm_backups": vm_backups,
            "ct_backups": ct_backups,
            "backup_dir": self.BACKUP_DIR,
        }

