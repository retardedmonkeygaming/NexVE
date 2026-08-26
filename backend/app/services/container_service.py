import subprocess
import os
import json
from typing import List, Optional


class ContainerService:
    def run_cmd(self, cmd: str) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            stderr = r.stderr.strip()
            if 'not found' in stderr.lower() or 'command not found' in stderr.lower():
                return {"success": False, "stdout": "", "stderr": f"Command not available: {cmd.split()[0]}. Install lxc-utils and pct."}
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Timeout"}
        except FileNotFoundError:
            return {"success": False, "stdout": "", "stderr": f"Command not found: {cmd.split()[0]}"}

    def list_templates(self) -> List[dict]:
        r = self.run_cmd("pveam list local")
        templates = []
        if r["success"]:
            for line in r["stdout"].splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    templates.append({"id": parts[0], "name": parts[1], "status": "ready"})
        # Fallback defaults
        if not templates:
            templates = [
                {"id": "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst", "name": "debian-12", "status": "ready"},
                {"id": "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst", "name": "ubuntu-24.04", "status": "ready"},
                {"id": "local:vztmpl/alpine-3.19-default_3.19-1_amd64.tar.zst", "name": "alpine-3.19", "status": "ready"},
            ]
        return templates

    def create_container(self, config: dict) -> dict:
        name = config["name"]
        ct_id = config.get("ct_id", 1000)
        hostname = config.get("hostname", name)
        vcpu = config.get("vcpu", 1)
        memory_mb = config.get("memory_mb", 512)
        swap_mb = config.get("swap_mb", 512)
        disk_gb = config.get("disk_gb", 8)
        template = config.get("template", "debian-12")
        ip_address = config.get("ip_address", "")
        unprivileged = config.get("unprivileged", True)
        nesting = config.get("nesting", False)
        mount_points = config.get("mount_points", "")
        cpu_weight = config.get("cpu_weight", 100)
        io_priority = config.get("io_priority", "normal")
        net_rate = config.get("net_rate", None)
        startup_order = config.get("startup_order", 0)
        shutdown_order = config.get("shutdown_order", 0)

        # Check if exists
        check = self.run_cmd(f"pct status {ct_id}")
        if check["success"]:
            return {"success": False, "error": f"Container ID {ct_id} already exists"}

        # Build network config
        net_config = "name=eth0,bridge=vmbr0,ip=dhcp"
        if ip_address:
            net_config = f"name=eth0,bridge=vmbr0,ip={ip_address}/24,gw=192.168.1.1"

        # Build mount point args
        mp_args = ""
        if mount_points:
            try:
                mps = json.loads(mount_points) if isinstance(mount_points, str) else mount_points
                for i, mp in enumerate(mps):
                    mp_args += f" -mp{mp.get('idx', i)}=volume={mp.get('volume', '')},mp={mp.get('mp', '')}"
            except (json.JSONDecodeError, TypeError):
                pass

        # Resource limit args
        rate_args = f" -rate {net_rate}" if net_rate else ""

        # Build create command
        cmd = (
            f"pct create {ct_id} "
            f"local:vztmpl/{template}.tar.zst "
            f"-hostname {hostname} "
            f"-cores {vcpu} "
            f"-memory {memory_mb} "
            f"-swap {swap_mb} "
            f"-rootfs local-lvm:size={disk_gb}G "
            f"-net0 {net_config} "
            f"-unprivileged {'1' if unprivileged else '0'} "
            f"-features nesting={'1' if nesting else '0'} "
            f"{mp_args} {rate_args}"
        )

        # Add startup order if specified
        if startup_order or shutdown_order:
            cmd += f" -startup order={startup_order},down={shutdown_order}"

        r = self.run_cmd(cmd)
        if not r["success"]:
            return {"success": False, "error": r["stderr"] or r["stdout"]}

        return {"success": True, "container": {"ct_id": ct_id, "name": name}}

    def get_container_status(self, ct_id: int) -> str:
        r = self.run_cmd(f"pct status {ct_id}")
        if r["success"]:
            if "running" in r["stdout"]:
                return "running"
            elif "stopped" in r["stdout"]:
                return "stopped"
        return "unknown"

    def start_container(self, ct_id: int) -> dict:
        r = self.run_cmd(f"pct start {ct_id}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def stop_container(self, ct_id: int) -> dict:
        r = self.run_cmd(f"pct stop {ct_id}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def restart_container(self, ct_id: int) -> dict:
        self.run_cmd(f"pct stop {ct_id}")
        return self.start_container(ct_id)

    def delete_container(self, ct_id: int) -> dict:
        status = self.get_container_status(ct_id)
        if status == "running":
            self.stop_container(ct_id)
        r = self.run_cmd(f"pct destroy {ct_id} --purge")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def get_container_config(self, ct_id: int) -> dict:
        r = self.run_cmd(f"pct config {ct_id}")
        config = {}
        if r["success"]:
            for line in r["stdout"].splitlines():
                if ": " in line:
                    key, val = line.split(": ", 1)
                    config[key.strip()] = val.strip()
        return config

    def update_container(self, ct_id: int, config: dict) -> dict:
        updates = []
        if "vcpu" in config:
            updates.append(f"-cores {config['vcpu']}")
        if "memory_mb" in config:
            updates.append(f"-memory {config['memory_mb']}")
        if "swap_mb" in config:
            updates.append(f"-swap {config['swap_mb']}")
        if "cpu_weight" in config:
            updates.append(f"-cpu {config['cpu_weight']}")
        if "io_priority" in config:
            prio_map = {"low": "1", "normal": "5", "high": "7"}
            updates.append(f"-ioprio {prio_map.get(config['io_priority'], '5')}")
        if "net_rate" in config:
            if config["net_rate"]:
                updates.append(f"-rate {config['net_rate']}")
        if "hostname" in config:
            updates.append(f"-hostname {config['hostname']}")
        if "nesting" in config:
            updates.append(f"-features nesting={'1' if config['nesting'] else '0'}")
        if "unprivileged" in config:
            updates.append(f"-unprivileged {'1' if config['unprivileged'] else '0'}")

        if not updates:
            return {"success": True}

        cmd = f"pct set {ct_id} " + " ".join(updates)
        r = self.run_cmd(cmd)
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def add_mount_point(self, ct_id: int, idx: int, volume: str, mp: str) -> dict:
        r = self.run_cmd(f"pct set {ct_id} -mp{idx} volume={volume},mp={mp}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def remove_mount_point(self, ct_id: int, idx: int) -> dict:
        r = self.run_cmd(f"pct set {ct_id} -delete mp{idx}")
        return {"success": r["success"], "error": r["stderr"] if not r["success"] else None}

    def container_exec(self, ct_id: int, command: str) -> dict:
        r = self.run_cmd(f"pct exec {ct_id} -- {command}")
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def backup_container(self, ct_id: int, storage: str = "local") -> dict:
        r = self.run_cmd(f"vzdump {ct_id} --storage {storage} --compress zstd")
        return {"success": r["success"], "stdout": r["stdout"], "stderr": r["stderr"]}

    def restore_container(self, ct_id: int, archive: str) -> dict:
        r = self.run_cmd(f"pct restore {ct_id} {archive}")
        return {"success": r["success"], "stderr": r["stderr"] if not r["success"] else None}
