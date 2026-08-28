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

    # ── VZDump Integration ──

    def vzdump_status(self) -> dict:
        """Check if vzdump is available."""
        r = self.run_cmd("which vzdump 2>/dev/null")
        return {"available": r["success"], "path": r["stdout"] if r["success"] else ""}

    def vzdump_backup(self, vm_id: int, mode: str = "snapshot", compress: str = "zstd",
                     storage: str = "", remove_old: bool = False, tmpdir: str = "") -> dict:
        """Run vzdump for a VM or container."""
        cmd = f"vzdump {vm_id} --mode {mode} --compress {compress}"
        if storage:
            cmd += f" --storage {storage}"
        if remove_old:
            cmd += " --remove"
        if tmpdir:
            cmd += f" --tmpdir {tmpdir}"
        cmd += " --quiet 1"
        r = self.run_cmd(cmd, timeout=3600)
        if r["success"]:
            # Parse log for backup path
            backup_path = ""
            for line in (r["stdout"] + "\n" + r["stderr"]).splitlines():
                if " backup " in line.lower() and (".tar" in line or ".vma" in line):
                    parts = line.split()
                    for p in parts:
                        if os.path.exists(p) or p.startswith("/"):
                            backup_path = p
                            break
            return {"success": True, "output": r["stdout"], "path": backup_path}
        return {"success": False, "error": r["stderr"] or r["stdout"]}

    def vzdump_restore(self, vm_id: int, archive_path: str) -> dict:
        """Restore a VM/container from a vzdump archive."""
        if not os.path.exists(archive_path):
            return {"success": False, "error": "Archive not found"}
        # Determine restore command based on archive type
        if ".vma" in archive_path or ".vma.zst" in archive_path:
            cmd = f"qmrestore {archive_path} {vm_id} --force 2>/dev/null || pct restore {vm_id} {archive_path} --ignore-unpack-errors 2>/dev/null"
        elif archive_path.endswith(".tar.gz") or archive_path.endswith(".tar.zst"):
            cmd = f"qmrestore {archive_path} {vm_id} --force 2>/dev/null || pct restore {vm_id} {archive_path} --ignore-unpack-errors 2>/dev/null"
        else:
            return {"success": False, "error": f"Unsupported archive format: {archive_path}"}
        r = self.run_cmd(cmd, timeout=3600)
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else "", "output": r["stdout"]}

    def vzdump_verify(self, archive_path: str) -> dict:
        """Verify integrity of a vzdump backup archive."""
        if not os.path.exists(archive_path):
            return {"success": False, "error": "Archive not found", "valid": False}
        if ".vma" in archive_path:
            cmd = f"vma verify {archive_path} 2>&1"
        elif archive_path.endswith(".tar.gz"):
            cmd = f"tar tzf {archive_path} > /dev/null 2>&1 && echo OK"
        elif archive_path.endswith(".tar.zst"):
            cmd = f"tar --zstd -tf {archive_path} > /dev/null 2>&1 && echo OK"
        else:
            return {"success": False, "error": "Unsupported format", "valid": False}
        r = self.run_cmd(cmd, timeout=300)
        return {"success": r["success"], "valid": r["success"] and "OK" in r["stdout"], "output": r["stdout"]}

    def vzdump_retention(self, vm_id: int, max_backups: int = 3) -> dict:
        """Apply retention policy — keep only N most recent backups for a VM."""
        backups = self.list_backups()
        vm_backups = sorted(
            [b for b in backups if b.get("type") == "vm" and str(b.get("vm_id", "")) == str(vm_id)],
            key=lambda x: x.get("created", ""),
            reverse=True
        )
        if len(vm_backups) <= max_backups:
            return {"success": True, "deleted": 0}
        to_delete = vm_backups[max_backups:]
        deleted = 0
        for b in to_delete:
            path = b.get("path") or b.get("filename", "")
            if path and os.path.exists(path):
                os.remove(path)
                deleted += 1
        return {"success": True, "deleted": deleted}

    # ── PBS (Proxmox Backup Server) Full API ──

    def pbs_status(self) -> dict:
        """Check if PBS client tools are available and configured."""
        r = self.run_cmd("which proxmox-backup-client 2>/dev/null || which pxar 2>/dev/null")
        # Check for configured repositories
        repo_file = "/etc/proxmox-backup/pbs.repo"
        configured = os.path.exists(repo_file)
        # Check running PBS daemon
        pr = subprocess.run("systemctl is-active proxmox-backup 2>/dev/null",
                          shell=True, capture_output=True, text=True, timeout=5)
        daemon_running = pr.stdout.strip() == "active"
        return {
            "client_available": r["success"],
            "daemon_running": daemon_running,
            "configured": configured,
        }

    def pbs_list_repositories(self) -> List[dict]:
        """List configured PBS repositories."""
        # Check common PBS config locations
        repos = []
        config_dir = "/etc/proxmox-backup"
        if os.path.isdir(config_dir):
            for f in os.listdir(config_dir):
                if f.endswith(".repo") or f.endswith(".pbs"):
                    try:
                        with open(os.path.join(config_dir, f)) as fh:
                            content = fh.read()
                        repos.append({"name": f, "config": content.strip()})
                    except Exception:
                        pass
        # Also check /etc/pve for PBS storage configs
        pve_dir = "/etc/pve"
        if os.path.isdir(pve_dir):
            for f in os.listdir(pve_dir):
                if "pbs" in f.lower():
                    try:
                        with open(os.path.join(pve_dir, f)) as fh:
                            content = fh.read()
                        repos.append({"name": f, "config": content.strip()})
                    except Exception:
                        pass
        return repos

    def pbs_backup(self, vm_id: int, repository: str = "", password: str = "",
                   backup_type: str = "vm", compress: str = "zstd") -> dict:
        """Backup a VM/container to PBS using proxmox-backup-client."""
        # Try proxmox-backup-client first, then fall back to pxar
        client = "proxmox-backup-client"
        r = self.run_cmd(f"which {client} 2>/dev/null")
        if not r["success"]:
            client = "pxar"
            r2 = self.run_cmd(f"which {client} 2>/dev/null")
            if not r2["success"]:
                return {"success": False, "error": "No PBS client found. Install proxmox-backup-client."}

        # Create backup archive first
        result = self.backup_vm(vm_id, compress=(compress != "none"))
        if not result.get("success"):
            return result
        backup_path = result.get("path", "")
        if not backup_path:
            return {"success": False, "error": "Backup path empty"}

        # Push to PBS
        if client == "proxmox-backup-client" and repository:
            backup_name = os.path.basename(backup_path)
            cmd = f"proxmox-backup-client backup {backup_name}={backup_path} --repository {repository}"
            if password:
                cmd += f" --keyfile /dev/stdin"
            r = self.run_cmd(cmd, timeout=3600)
            if r["success"]:
                return {"success": True, "path": backup_path, "pbs_repository": repository, "output": r["stdout"]}
            return {"success": False, "error": r["stderr"]}
        else:
            # pxar fallback
            pxar_path = f"{backup_path}.pxar"
            r = self.run_cmd(f'pxar create "{pxar_path}" "{backup_path}"')
            if r["success"]:
                return {"success": True, "path": pxar_path, "pbs_repository": repository}
            return {"success": False, "error": r["stderr"]}

    def pbs_restore(self, repository: str, backup_snapshot: str, vm_id: int) -> dict:
        """Restore from PBS."""
        client = "proxmox-backup-client"
        r = self.run_cmd(f"which {client} 2>/dev/null")
        if not r["success"]:
            return {"success": False, "error": "proxmox-backup-client not found"}

        restore_dir = f"/tmp/pbs-restore-{vm_id}"
        os.makedirs(restore_dir, exist_ok=True)
        cmd = f"proxmox-backup-client restore {backup_snapshot} --repository {repository} --target {restore_dir}"
        r = self.run_cmd(cmd, timeout=3600)
        if not r["success"]:
            return {"success": False, "error": r["stderr"]}

        # Find the restored archive and restore it
        for f in os.listdir(restore_dir):
            archive = os.path.join(restore_dir, f)
            if os.path.isfile(archive):
                return self.vzdump_restore(vm_id, archive)
        return {"success": False, "error": "No archive found after PBS restore"}

    def pbs_live_restore(self, repository: str, backup_snapshot: str, vm_id: int) -> dict:
        """Live-restore: start VM while data is still being restored."""
        client = "proxmox-backup-client"
        r = self.run_cmd(f"which {client} 2>/dev/null")
        if not r["success"]:
            return {"success": False, "error": "proxmox-backup-client not found"}

        restore_dir = f"/var/lib/libvirt/images/pbs-live-{vm_id}"
        os.makedirs(restore_dir, exist_ok=True)
        # Start background restore
        cmd = (f"nohup proxmox-backup-client restore {backup_snapshot} "
               f"--repository {repository} --target {restore_dir} "
               f"> {restore_dir}/restore.log 2>&1 &")
        self.run_cmd(cmd, timeout=10)
        return {
            "success": True,
            "message": "Live restore started in background",
            "restore_dir": restore_dir,
            "log": f"{restore_dir}/restore.log",
        }

    def pbs_list_snapshots(self, repository: str) -> List[dict]:
        """List snapshots in a PBS repository."""
        client = "proxmox-backup-client"
        cmd = f"proxmox-backup-client snapshots --repository {repository} 2>&1"
        r = self.run_cmd(cmd, timeout=30)
        snapshots = []
        if r["success"]:
            for line in r["stdout"].splitlines():
                if line.strip() and not line.startswith("Using"):
                    snapshots.append({"raw": line.strip()})
        return snapshots

    def pbs_prune(self, repository: str, keep_daily: int = 7, keep_weekly: int = 4,
                  keep_monthly: int = 6) -> dict:
        """Prune old backups in PBS repository."""
        cmd = (f"proxmox-backup-client prune --repository {repository} "
               f"--keep-daily {keep_daily} --keep-weekly {keep_weekly} "
               f"--keep-monthly {keep_monthly} 2>&1")
        r = self.run_cmd(cmd, timeout=300)
        return {"success": r["success"], "output": r["stdout"], "error": r["stderr"]}

    def pbs_gc(self, repository: str) -> dict:
        """Run garbage collection on PBS repository."""
        cmd = f"proxmox-backup-client gc --repository {repository} 2>&1"
        r = self.run_cmd(cmd, timeout=3600)
        return {"success": r["success"], "output": r["stdout"], "error": r["stderr"]}

    def pbs_info(self, repository: str) -> dict:
        """Get PBS repository info."""
        cmd = f"proxmox-backup-client info --repository {repository} 2>&1"
        r = self.run_cmd(cmd, timeout=30)
        return {"success": r["success"], "output": r["stdout"], "error": r["stderr"]}

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

