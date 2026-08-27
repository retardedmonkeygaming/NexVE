"""
NexVE Container Service v3.1
Uses standard LXC commands (lxc-*) for container management.
Supports lxc-download template (preferred) and debootstrap fallback.
"""
import subprocess
import os
import json
from typing import List, Optional


class ContainerService:
    def run_cmd(self, cmd: str, timeout: int = 30) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out"}
        except FileNotFoundError:
            return {"success": False, "stdout": "", "stderr": f"Command not found: {cmd.split()[0]}"}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e)}

    def _has_lxc(self) -> bool:
        """Check if LXC tools are available."""
        r = self.run_cmd("which lxc-ls 2>/dev/null || which lxc-info 2>/dev/null")
        return r["success"]

    def _has_lxc_attach(self) -> bool:
        r = self.run_cmd("which lxc-attach 2>/dev/null")
        return r["success"]

    def _has_download_template(self) -> bool:
        """Check if lxc-download template is available."""
        r = self.run_cmd("ls /usr/share/lxc/templates/lxc-download 2>/dev/null || which lxc-download 2>/dev/null")
        return r["success"]

    def _get_lxc_version(self) -> str:
        """Get LXC version."""
        r = self.run_cmd("lxc-ls --version 2>/dev/null || lxc-info --version 2>/dev/null")
        return r["stdout"] if r["success"] else "unknown"

    def _list_download_templates(self, dist: str) -> List[str]:
        """List available releases for a distribution via lxc-download."""
        r = self.run_cmd(
            f"lxc-download --list --dist {dist} 2>/dev/null",
            timeout=30
        )
        releases = []
        if r["success"]:
            for line in r["stdout"].splitlines():
                line = line.strip()
                if line and not line.startswith("DIST") and not line.startswith("-"):
                    parts = line.split()
                    if len(parts) >= 2:
                        releases.append(parts[1])  # RELEASE column
        return releases

    def list_templates(self) -> List[dict]:
        """List available LXC templates."""
        templates = [
            {"id": "debian/bookworm", "name": "Debian 12 (Bookworm)", "status": "available", "dist": "debian", "release": "bookworm"},
            {"id": "debian/bullseye", "name": "Debian 11 (Bullseye)", "status": "available", "dist": "debian", "release": "bullseye"},
            {"id": "ubuntu/jammy", "name": "Ubuntu 22.04 (Jammy)", "status": "available", "dist": "ubuntu", "release": "jammy"},
            {"id": "ubuntu/noble", "name": "Ubuntu 24.04 (Noble)", "status": "available", "dist": "ubuntu", "release": "noble"},
            {"id": "ubuntu/focal", "name": "Ubuntu 20.04 (Focal)", "status": "available", "dist": "ubuntu", "release": "focal"},
            {"id": "alpine/3.19", "name": "Alpine Linux 3.19", "status": "available", "dist": "alpine", "release": "3.19"},
            {"id": "alpine/3.20", "name": "Alpine Linux 3.20", "status": "available", "dist": "alpine", "release": "3.20"},
            {"id": "fedora/39", "name": "Fedora 39", "status": "available", "dist": "fedora", "release": "39"},
            {"id": "fedora/40", "name": "Fedora 40", "status": "available", "dist": "fedora", "release": "40"},
            {"id": "centos/stream9", "name": "CentOS Stream 9", "status": "available", "dist": "centos", "release": "stream9"},
            {"id": "rockylinux/9", "name": "Rocky Linux 9", "status": "available", "dist": "rockylinux", "release": "9"},
            {"id": "almalinux/9", "name": "AlmaLinux 9", "status": "available", "dist": "almalinux", "release": "9"},
        ]
        return templates

    def get_system_info(self) -> dict:
        """Get LXC system information for diagnostics."""
        info = {
            "has_lxc": self._has_lxc(),
            "has_lxc_attach": self._has_lxc_attach(),
            "has_download_template": self._has_download_template(),
            "lxc_version": self._get_lxc_version(),
            "is_root": os.geteuid() == 0,
        }
        # Check for common issues
        issues = []
        if not info["has_lxc"]:
            issues.append("LXC tools not found. Install: apt install lxc-utils")
        if not info["has_download_template"]:
            issues.append("lxc-download template not found. Install: apt install lxc")
        if not info["is_root"]:
            issues.append("Not running as root. Containers require root privileges.")
        info["issues"] = issues
        return info

    def create_container(self, config: dict) -> dict:
        """Create a new LXC container using the download template."""
        name = config["name"]
        ct_id = config.get("ct_id", 1000)
        hostname = config.get("hostname", name)
        vcpu = config.get("vcpu", 1)
        memory_mb = config.get("memory_mb", 512)
        swap_mb = config.get("swap_mb", 512)
        disk_gb = config.get("disk_gb", 8)
        template = config.get("template", "debian/bookworm")
        ip_address = config.get("ip_address", "")
        unprivileged = config.get("unprivileged", True)
        nesting = config.get("nesting", False)

        # Parse dist/release from template id (e.g., "debian/bookworm" -> dist="debian", release="bookworm")
        if "/" in template:
            parts = template.split("/")
            dist = parts[0]
            release = parts[1]
        else:
            dist = template
            release = "latest"

        # Pre-flight checks
        if not self._has_lxc():
            return {
                "success": False,
                "error": "LXC tools are not installed on this system.",
                "hint": "Install LXC: apt install lxc-utils lxc\nOn Debian/Ubuntu: apt install lxc debootstrap\nOn RHEL/Fedora: dnf install lxc"
            }

        if not os.geteuid() == 0:
            return {
                "success": False,
                "error": "Container creation requires root privileges.",
                "hint": "Run NexVE as root or with sudo."
            }

        # Check if container already exists
        check = self.run_cmd(f"lxc-info -n {name} 2>/dev/null")
        if check["success"] and ("RUNNING" in check["stdout"].upper() or "STOPPED" in check["stdout"].upper()):
            return {"success": False, "error": f"Container '{name}' already exists"}

        # Remove leftover config if any
        self.run_cmd(f"lxc-destroy -n {name} 2>/dev/null")

        # Method 1: Try lxc-download template (preferred — downloads a rootfs tarball)
        if self._has_download_template():
            dl_cmd = (
                f"lxc-create -n {name} -t download"
                f" -- --dist {dist} --release {release} --arch amd64 --no-validate"
            )
            r = self.run_cmd(dl_cmd, timeout=180)
            if r["success"]:
                return self._post_create(config, name, ct_id, hostname, vcpu, memory_mb, swap_mb, ip_address, unprivileged, nesting)
            # If download fails, log the error but continue to fallback
            dl_error = r["stderr"] or r["stdout"]

        else:
            dl_error = "lxc-download template not available"

        # Method 2: Try debootstrap directly (works on Debian/Ubuntu)
        debootstrap_check = self.run_cmd("which debootstrap 2>/dev/null")
        if debootstrap_check["success"]:
            deb_cmd = f"lxc-create -n {name} -t debian -- --release bookworm"
            r = self.run_cmd(deb_cmd, timeout=180)
            if r["success"]:
                return self._post_create(config, name, ct_id, hostname, vcpu, memory_mb, swap_mb, ip_address, unprivileged, nesting)
            deb_error = r["stderr"] or r["stdout"]
        else:
            deb_error = "debootstrap not available"

        # Method 3: Try creating a minimal container with busybox (last resort)
        busybox_check = self.run_cmd("which busybox 2>/dev/null")
        if busybox_check["success"]:
            bb_cmd = f"lxc-create -n {name} -t busybox"
            r = self.run_cmd(bb_cmd, timeout=60)
            if r["success"]:
                return self._post_create(config, name, ct_id, hostname, vcpu, memory_mb, swap_mb, ip_address, unprivileged, nesting)

        # All methods failed
        return {
            "success": False,
            "error": f"Failed to create container '{name}'. All template methods failed.",
            "details": {
                "download_template": dl_error,
                "debootstrap": deb_error if debootstrap_check.get("success") else "not installed",
            },
            "hint": (
                "To fix this:\n"
                "1. Install LXC with download support: apt install lxc debootstrap\n"
                "2. Ensure network access for downloading rootfs images\n"
                "3. Try a different template (e.g., debian/bookworm is most reliable)\n"
                "4. Check: lxc-create -t download -n test -- --dist debian --release bookworm"
            )
        }

    def _post_create(self, config, name, ct_id, hostname, vcpu, memory_mb, swap_mb, ip_address, unprivileged, nesting):
        """Apply post-creation configuration to a container."""
        config_path = f"/var/lib/lxc/{name}/config"
        try:
            extra = f"\n# NexVE Configuration\n"
            extra += f"lxc.uts.name = {hostname}\n"

            if vcpu:
                cpu_quota = vcpu * 100000
                extra += f"lxc.cgroup2.cpu.max = {cpu_quota} 100000\n"

            if memory_mb:
                mem_bytes = memory_mb * 1024 * 1024
                extra += f"lxc.cgroup2.memory.max = {mem_bytes}\n"

            if swap_mb:
                swap_bytes = swap_mb * 1024 * 1024
                extra += f"lxc.cgroup2.memory.swap.max = {swap_bytes}\n"

            extra += "lxc.net.0.type = veth\n"
            extra += "lxc.net.0.link = lxcbr0\n"
            extra += "lxc.net.0.flags = up\n"
            if ip_address:
                extra += f"lxc.net.0.ipv4.address = {ip_address}/24\n"

            if nesting:
                extra += "lxc.sysctl.kernel.unprivileged_userns_clone = 1\n"
                extra += "lxc.apparmor.profile = unconfined\n"

            if not unprivileged:
                extra += "lxc.idmap = u 0 0 65536\n"
                extra += "lxc.idmap = g 0 0 65536\n"

            with open(config_path, "a") as f:
                f.write(extra)
        except Exception as e:
            return {
                "success": True,
                "container": {"ct_id": ct_id, "name": name, "hostname": hostname},
                "warning": f"Container created but config update failed: {e}"
            }

        return {"success": True, "container": {"ct_id": ct_id, "name": name, "hostname": hostname}}

    def get_container_status(self, ct_id: int) -> str:
        r = self.run_cmd(f"lxc-info -n {ct_id} --state 2>/dev/null")
        if r["success"]:
            stdout = r["stdout"].upper()
            if "RUNNING" in stdout:
                return "running"
            elif "STOPPED" in stdout:
                return "stopped"
            elif "FROZEN" in stdout:
                return "paused"
        return "unknown"

    def get_container_status_by_name(self, name: str) -> str:
        r = self.run_cmd(f"lxc-info -n {name} --state 2>/dev/null")
        if r["success"]:
            stdout = r["stdout"].upper()
            if "RUNNING" in stdout:
                return "running"
            elif "STOPPED" in stdout:
                return "stopped"
            elif "FROZEN" in stdout:
                return "paused"
        return "unknown"

    def start_container(self, ct_id: int) -> dict:
        r = self.run_cmd(f"lxc-start -n {ct_id}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def start_container_by_name(self, name: str) -> dict:
        r = self.run_cmd(f"lxc-start -n {name}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def stop_container(self, ct_id: int) -> dict:
        r = self.run_cmd(f"lxc-stop -n {ct_id} -t 30")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def stop_container_by_name(self, name: str) -> dict:
        r = self.run_cmd(f"lxc-stop -n {name} -t 30")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def restart_container(self, ct_id: int) -> dict:
        self.run_cmd(f"lxc-stop -n {ct_id} -t 10")
        return self.start_container(ct_id)

    def restart_container_by_name(self, name: str) -> dict:
        self.run_cmd(f"lxc-stop -n {name} -t 10")
        return self.start_container_by_name(name)

    def delete_container(self, ct_id: int) -> dict:
        status = self.get_container_status(ct_id)
        if status == "running":
            self.stop_container(ct_id)
        r = self.run_cmd(f"lxc-destroy -n {ct_id}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def delete_container_by_name(self, name: str) -> dict:
        status = self.get_container_status_by_name(name)
        if status == "running":
            self.stop_container_by_name(name)
        r = self.run_cmd(f"lxc-destroy -n {name}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def get_container_config(self, ct_id: int) -> dict:
        r = self.run_cmd(f"lxc-info -n {ct_id} 2>/dev/null")
        config = {}
        if r["success"]:
            for line in r["stdout"].splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    config[key.strip()] = val.strip()

        config_file = f"/var/lib/lxc/{ct_id}/config"
        if os.path.exists(config_file):
            try:
                with open(config_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            config[key.strip()] = val.strip()
            except Exception:
                pass
        return config

    def get_container_config_by_name(self, name: str) -> dict:
        r = self.run_cmd(f"lxc-info -n {name} 2>/dev/null")
        config = {}
        if r["success"]:
            for line in r["stdout"].splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    config[key.strip()] = val.strip()

        config_file = f"/var/lib/lxc/{name}/config"
        if os.path.exists(config_file):
            try:
                with open(config_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            config[key.strip()] = val.strip()
            except Exception:
                pass
        return config

    def update_container(self, ct_id: int, config: dict) -> dict:
        updates = []
        if "vcpu" in config and config["vcpu"]:
            cpu_quota = int(config["vcpu"]) * 100000
            updates.append(f"lxc.cgroup2.cpu.max = {cpu_quota} 100000")
        if "memory_mb" in config and config["memory_mb"]:
            mem_bytes = int(config["memory_mb"]) * 1024 * 1024
            updates.append(f"lxc.cgroup2.memory.max = {mem_bytes}")
        if "swap_mb" in config and config["swap_mb"]:
            swap_bytes = int(config["swap_mb"]) * 1024 * 1024
            updates.append(f"lxc.cgroup2.memory.swap.max = {swap_bytes}")
        if "hostname" in config:
            updates.append(f"lxc.uts.name = {config['hostname']}")
        if "nesting" in config:
            if config["nesting"]:
                updates.append("lxc.sysctl.kernel.unprivileged_userns_clone = 1")
                updates.append("lxc.apparmor.profile = unconfined")
            else:
                updates.append("lxc.apparmor.profile = lxc-container-default-cgns")

        if not updates:
            return {"success": True}

        config_path = f"/var/lib/lxc/{ct_id}/config"
        try:
            existing = {}
            if os.path.exists(config_path):
                with open(config_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            existing[key.strip()] = val.strip()

            for update in updates:
                if "=" in update:
                    key, val = update.split("=", 1)
                    existing[key.strip()] = val.strip()

            with open(config_path, "w") as f:
                for key, val in existing.items():
                    f.write(f"{key} = {val}\n")

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_mount_point(self, ct_id: int, idx: int, volume: str, mp: str) -> dict:
        config_path = f"/var/lib/lxc/{ct_id}/config"
        try:
            with open(config_path, "a") as f:
                f.write(f"\nlxc.mount.entry = {volume} {mp.lstrip('/')} none bind 0 0\n")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_mount_point(self, ct_id: int, idx: int) -> dict:
        config_path = f"/var/lib/lxc/{ct_id}/config"
        try:
            if os.path.exists(config_path):
                with open(config_path) as f:
                    lines = f.readlines()
                with open(config_path, "w") as f:
                    for line in lines:
                        if not line.strip().startswith("lxc.mount.entry"):
                            f.write(line)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def container_exec(self, ct_id: int, command: str) -> dict:
        r = self.run_cmd(f"lxc-attach -n {ct_id} -- {command}", timeout=30)
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def container_exec_by_name(self, name: str, command: str) -> dict:
        r = self.run_cmd(f"lxc-attach -n {name} -- {command}", timeout=30)
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def backup_container(self, ct_id: int, storage: str = "local") -> dict:
        self.run_cmd(f"lxc-stop -n {ct_id} -t 10", timeout=30)
        backup_dir = "/var/lib/nexve/backups"
        os.makedirs(backup_dir, exist_ok=True)
        r = self.run_cmd(
            f"tar czf {backup_dir}/{ct_id}_$(date +%Y%m%d_%H%M%S).tar.gz -C /var/lib/lxc/{ct_id}/rootfs .",
            timeout=300
        )
        self.start_container(ct_id)
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def restore_container(self, ct_id: int, archive: str) -> dict:
        rootfs_path = f"/var/lib/lxc/{ct_id}/rootfs"
        os.makedirs(rootfs_path, exist_ok=True)
        r = self.run_cmd(f"tar xzf {archive} -C {rootfs_path}", timeout=300)
        return {"success": r["success"], "stderr": r["stderr"] if not r["success"] else None}
