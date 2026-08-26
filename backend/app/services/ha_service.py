"""
NexVE High Availability Service
Manages HA groups, guest failover, and cluster HA configuration.
"""
import subprocess
from typing import List, Optional
from datetime import datetime


class HAService:
    """Manages High Availability configuration."""

    def get_ha_status(self) -> dict:
        """Get overall HA cluster status."""
        try:
            # Check if HA manager is running
            r = subprocess.run(
                "systemctl is-active ha-manager 2>/dev/null || echo inactive",
                shell=True, capture_output=True, text=True, timeout=5
            )
            ha_active = r.stdout.strip() == "active"

            # Get HA resources
            r2 = subprocess.run(
                "ha-manager status 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )

            return {
                "active": ha_active,
                "status_text": r2.stdout.strip() if r2.returncode == 0 else "unknown",
            }
        except Exception:
            return {"active": False, "status_text": "unavailable"}

    def get_ha_groups(self) -> List[dict]:
        """Get HA group configuration."""
        try:
            r = subprocess.run(
                "ha-manager groups 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            groups = []
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.splitlines():
                    if line.strip():
                        groups.append({"name": line.strip(), "type": "group"})
            return groups
        except Exception:
            return []

    def get_ha_resources(self) -> List[dict]:
        """Get HA-managed resources."""
        try:
            r = subprocess.run(
                "ha-manager resources 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            resources = []
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        resources.append({
                            "sid": parts[0],
                            "type": parts[1] if len(parts) > 1 else "",
                            "status": parts[2] if len(parts) > 2 else "",
                        })
            return resources
        except Exception:
            return []

    def add_ha_resource(self, vm_id: int, vm_type: str = "vm", 
                       group: str = "", max_restart: int = 3) -> dict:
        """Add a VM/container to HA management."""
        try:
            sid = f"{vm_type}/{vm_id}"
            cmd = f"ha-manager add {sid}"
            if group:
                cmd += f" --group {group}"
            cmd += f" --max_restart {max_restart}"

            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_ha_resource(self, vm_id: int, vm_type: str = "vm") -> dict:
        """Remove a VM/container from HA management."""
        try:
            sid = f"{vm_type}/{vm_id}"
            r = subprocess.run(
                f"ha-manager remove {sid}",
                shell=True, capture_output=True, text=True, timeout=10
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ha_restart(self, vm_id: int, vm_type: str = "vm") -> dict:
        """Request HA manager to restart a guest."""
        try:
            sid = f"{vm_type}/{vm_id}"
            r = subprocess.run(
                f"ha-manager crashdump {sid}",
                shell=True, capture_output=True, text=True, timeout=10
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def migrate_resource(self, vm_id: int, target_node: str, 
                        vm_type: str = "vm") -> dict:
        """Migrate an HA resource to another node."""
        try:
            sid = f"{vm_type}/{vm_id}"
            r = subprocess.run(
                f"ha-manager migrate {sid} {target_node}",
                shell=True, capture_output=True, text=True, timeout=10
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}
