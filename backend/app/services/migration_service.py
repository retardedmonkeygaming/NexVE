"""
NexVE Migration Service
Handles live migration of VMs and containers between cluster nodes.
"""
import subprocess
import re
from datetime import datetime
from typing import Optional, List


class MigrationService:
    """Manages live migration of VMs/containers between nodes."""

    def get_nodes(self) -> List[dict]:
        """Get available nodes for migration."""
        try:
            r = subprocess.run(
                "virsh list --all --name 2>/dev/null | head -1; hostname",
                shell=True, capture_output=True, text=True, timeout=5
            )
            # Get local hostname
            hostname_r = subprocess.run(
                "hostname", shell=True, capture_output=True, text=True, timeout=5
            )
            local_hostname = hostname_r.stdout.strip() if hostname_r.returncode == 0 else "unknown"

            # Check if clustered
            cluster_r = subprocess.run(
                "virsh list --all --name 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )

            return [{
                "name": local_hostname,
                "address": "localhost",
                "status": "online",
                "local": True,
            }]
        except Exception:
            return []

    def migrate_vm(self, vm_name: str, target_node: str, live: bool = True, 
                   force: bool = False) -> dict:
        """Migrate a VM to another node."""
        try:
            # Check if VM exists locally
            check = subprocess.run(
                f"virsh dominfo {vm_name} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=10
            )
            if check.returncode != 0:
                return {"success": False, "error": f"VM '{vm_name}' not found locally"}

            # Build migration command
            flags = []
            if live:
                flags.append("--live")
            if force:
                flags.append("--force")
            flags.append("--verbose")

            flag_str = " ".join(flags)

            # For same-node migration (defining on different driver)
            # For remote migration, use --dest
            if target_node in ("localhost", "127.0.0.1"):
                return {"success": False, "error": "Cannot migrate to same node"}

            cmd = f"virsh migrate {flag_str} {vm_name} qemu+ssh://{target_node}/system"

            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                return {"success": True, "message": f"VM '{vm_name}' migrated to {target_node}"}
            else:
                return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Migration timed out after 5 minutes"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_migration_status(self, vm_name: str) -> dict:
        """Get migration status for a VM."""
        try:
            r = subprocess.run(
                f"virsh domjobinfo {vm_name} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout.strip():
                info = {}
                for line in r.stdout.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        info[k.strip()] = v.strip()
                return {"active": True, "info": info}
            return {"active": False}
        except Exception:
            return {"active": False}

    def cancel_migration(self, vm_name: str) -> dict:
        """Cancel an in-progress migration."""
        try:
            r = subprocess.run(
                f"virsh domjobabort {vm_name}",
                shell=True, capture_output=True, text=True, timeout=10
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def migrate_container(self, ct_id: int, target_node: str) -> dict:
        """Migrate a container to another node (requires pct)."""
        try:
            # Check if pct is available
            pct_check = subprocess.run(
                "which pct", shell=True, capture_output=True, text=True
            )
            if pct_check.returncode != 0:
                return {"success": False, "error": "pct (Proxmox tool) not available"}

            # pct migrate requires cluster setup
            r = subprocess.run(
                f"pct migrate {ct_id} {target_node}",
                shell=True, capture_output=True, text=True, timeout=300
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}
