"""
NexVE Container Service v3.0
Uses standard LXC commands (lxc-*) for container management.
Replaces proprietary Proxmox PCT commands.
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

    def list_templates(self) -> List[dict]:
        """List available LXC templates."""
        # Check for downloaded rootfs tarballs in common locations
        templates = []
        search_dirs = [
            "/var/cache/lxc/templates",
            "/var/lib/lxc/templates",
            os.path.expanduser("~/.cache/lxc/templates"),
            "/usr/share/lxc/templates",
        ]
        found_any = False
        for d in search_dirs:
            if os.path.isdir(d):
                for f in sorted(os.listdir(d)):
                    if f.endswith((".tar.gz", ".tar.xz", ".tar.zst", ".tar.bz2")):
                        templates.append({
                            "id": f,
                            "name": f.split("_")[0].replace("-rootfs", ""),
                            "status": "ready",
                        })
                        found_any = True

        # Fallback: suggest popular distro rootfs images
        if not found_any:
            templates = [
                {"id": "debian-12", "name": "debian-12 (download)", "status": "available"},
                {"id": "ubuntu-24.04", "name": "ubuntu-24.04 (download)", "status": "available"},
                {"id": "alpine-3.19", "name": "alpine-3.19 (download)", "status": "available"},
                {"id": "fedora-39", "name": "fedora-39 (download)", "status": "available"},
                {"id": "centos-stream9", "name": "centos-stream9 (download)", "status": "available"},
            ]
        return templates

    def create_container(self, config: dict) -> dict:
        """Create a new LXC container using debootstrap or lxc-create."""
        name = config["name"]
        ct_id = config.get("ct_id", 1000)
        hostname = config.get("hostname", name)
        vcpu = config.get("vcpu", 1)
        memory_mb = config.get("memory_mb", 512)
        swap_mb = config.get("swap_mb", 512)
        disk_gb = config.get("disk_gb", 8)
        template = config.get("template", "debian")
        ip_address = config.get("ip_address", "")
        unprivileged = config.get("unprivileged", True)
        nesting = config.get("nesting", False)
        mount_points = config.get("mount_points", "")
        cpu_weight = config.get("cpu_weight", 100)
        io_priority = config.get("io_priority", "normal")

        # Check if container already exists
        check = self.run_cmd(f"lxc-info -n {name} 2>/dev/null")
        if check["success"] and "stopped" in check["stdout"]:
            return {"success": False, "error": f"Container '{name}' already exists"}

        # Determine template name for lxc-create
        template_lower = template.lower().replace(".tar.gz", "").replace(".tar.xz", "")
        if "debian" in template_lower:
            lxc_template = "debian"
        elif "ubuntu" in template_lower:
            lxc_template = "ubuntu"
        elif "alpine" in template_lower:
            lxc_template = "alpine"
        elif "fedora" in template_lower:
            lxc_template = "fedora"
        elif "centos" in template_lower:
            lxc_template = "centos"
        else:
            lxc_template = "download"

        # Build LXC configuration
        lxc_dir = f"/var/lib/lxc/{name}"
        os.makedirs(lxc_dir, exist_ok=True)

        # Create container with lxc-create
        cmd = f"lxc-create -n {name} -t {lxc_template}"
        if lxc_template == "download":
            cmd += f" -- --dist {template_lower.split('-')[0]} --release {template_lower.split('-')[-1]} --arch amd64"
        else:
            cmd += f" -- --release {template_lower.split('-')[-1] if '-' in template_lower else 'latest'}"

        r = self.run_cmd(cmd, timeout=120)
        if not r["success"]:
            return {"success": False, "error": r["stderr"] or r["stdout"] or "Failed to create container"}

        # Write LXC config
        config_path = f"{lxc_dir}/config"
        config_content = f"""# NexVE LXC Container Configuration
lxc.uts.name = {hostname}
lxc.arch = amd64

# Resource limits
lxc.cgroup2.cpu.max = {vcpu * 100000} 100000
lxc.cgroup2.memory.max = {memory_mb * 1024 * 1024}
lxc.cgroup2.memory.swap.max = {swap_mb * 1024 * 1024}

# Networking
lxc.net.0.type = veth
lxc.net.0.link = vmbr0
lxc.net.0.flags = up
"""
        if ip_address:
            config_content += f"lxc.net.0.ipv4.address = {ip_address}/24\n"

        if nesting:
            config_content += "lxc.sysctl.kernel.unprivileged_userns_clone = 1\n"
            config_content += "lxc.apparmor.profile = unconfined\n"

        # Privileged container settings
        if not unprivileged:
            config_content += "lxc.idmap = u 0 0 65536\n"
            config_content += "lxc.idmap = g 0 0 65536\n"

        try:
            with open(config_path, "w") as f:
                f.write(config_content)
        except Exception as e:
            return {"success": False, "error": f"Failed to write config: {e}"}

        return {"success": True, "container": {"ct_id": ct_id, "name": name, "hostname": hostname}}

    def get_container_status(self, ct_id: int) -> str:
        """Get container status by name (ct_id used as name for LXC)."""
        # Try to find container by searching DB for the name
        # For now, use ct_id as name
        r = self.run_cmd(f"lxc-info -n {ct_id} --state 2>/dev/null")
        if r["success"]:
            if "RUNNING" in r["stdout"]:
                return "running"
            elif "STOPPED" in r["stdout"]:
                return "stopped"
            elif "FROZEN" in r["stdout"]:
                return "paused"
        return "unknown"

    def get_container_status_by_name(self, name: str) -> str:
        """Get container status by name."""
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
        """Get LXC container configuration."""
        r = self.run_cmd(f"lxc-info -n {ct_id} 2>/dev/null")
        config = {}
        if r["success"]:
            for line in r["stdout"].splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    config[key.strip()] = val.strip()

        # Also try to read the config file
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
        """Get LXC container configuration by name."""
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
        """Update container resource limits via cgroup."""
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

        # Write updates to config file
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

            # Apply updates
            for update in updates:
                if "=" in update:
                    key, val = update.split("=", 1)
                    existing[key.strip()] = val.strip()

            # Write back
            with open(config_path, "w") as f:
                for key, val in existing.items():
                    f.write(f"{key} = {val}\n")

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_mount_point(self, ct_id: int, idx: int, volume: str, mp: str) -> dict:
        """Add a mount point to a container."""
        config_path = f"/var/lib/lxc/{ct_id}/config"
        try:
            with open(config_path, "a") as f:
                f.write(f"\nlxc.mount.entry = {volume} {mp.lstrip('/')} none bind 0 0\n")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_mount_point(self, ct_id: int, idx: int) -> dict:
        """Remove a mount point from a container."""
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
        """Execute a command inside a running container."""
        r = self.run_cmd(f"lxc-attach -n {ct_id} -- {command}", timeout=30)
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def container_exec_by_name(self, name: str, command: str) -> dict:
        r = self.run_cmd(f"lxc-attach -n {name} -- {command}", timeout=30)
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def backup_container(self, ct_id: int, storage: str = "local") -> dict:
        """Snapshot a container."""
        r = self.run_cmd(f"lxc-stop -n {ct_id} -t 10", timeout=30)
        r = self.run_cmd(
            f"tar czf /var/lib/nexve/backups/{ct_id}_$(date +%Y%m%d_%H%M%S).tar.gz -C /var/lib/lxc/{ct_id}/rootfs .",
            timeout=300
        )
        self.start_container(ct_id)
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def restore_container(self, ct_id: int, archive: str) -> dict:
        """Restore a container from backup."""
        rootfs_path = f"/var/lib/lxc/{ct_id}/rootfs"
        os.makedirs(rootfs_path, exist_ok=True)
        r = self.run_cmd(f"tar xzf {archive} -C {rootfs_path}", timeout=300)
        return {"success": r["success"], "stderr": r["stderr"] if not r["success"] else None}
