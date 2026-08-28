"""
NexVE Cluster Service
Manages Corosync/Pacemaker cluster formation and node management.
"""
import subprocess
import os
import json
from typing import List


class ClusterService:
    """Manages cluster formation and node management."""

    def get_cluster_status(self) -> dict:
        """Get cluster status."""
        try:
            # Check corosync
            r = subprocess.run(
                "corosync-cfgtool -s 2>/dev/null || echo 'not clustered'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            is_clustered = "Ring ID" in r.stdout or "member" in r.stdout.lower()

            # Get node list
            nodes = self.get_nodes()

            # Get quorum
            q = subprocess.run(
                "corosync-quorumtool -s 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            quorum_info = {}
            if q.returncode == 0:
                for line in q.stdout.splitlines():
                    if "Nodes" in line:
                        quorum_info["nodes"] = line.split(":")[-1].strip()
                    elif "Ring" in line:
                        quorum_info["ring"] = line.strip()

            return {
                "clustered": is_clustered,
                "nodes": nodes,
                "quorum": quorum_info,
            }
        except Exception:
            return {"clustered": False, "nodes": [], "quorum": {}}

    def get_nodes(self) -> List[dict]:
        """Get cluster nodes."""
        try:
            r = subprocess.run(
                "corosync-cmapctl nodes.nodes 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            nodes = []
            if r.returncode == 0 and r.stdout.strip():
                current_name = ""
                for line in r.stdout.splitlines():
                    if ".name" in line and "=" in line:
                        current_name = line.split("=")[-1].strip().strip("'\"")
                    elif ".nodeid" in line and "=" in line and current_name:
                        nodeid = line.split("=")[-1].strip()
                        nodes.append({
                            "name": current_name,
                            "node_id": nodeid,
                            "status": "online",
                        })
                        current_name = ""
            return nodes
        except Exception:
            return []

    def create_cluster(self, cluster_name: str = "nexve") -> dict:
        """Initialize a new cluster on this node."""
        try:
            # Check if already clustered
            check = subprocess.run(
                "corosync-cfgtool -s 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if "Ring ID" in check.stdout:
                return {"success": False, "error": "Node is already part of a cluster"}

            # Create corosync config
            import socket
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)

            corosync_conf = f"""totem {{
    version: 2
    cluster_name: {cluster_name}
    transport: knet
    secauth: on
    crypto_cipher: aes256
    crypto_hash: sha256
}}

nodelist {{
    node {{
        ring_address: {ip}
        name: {hostname}
        nodeid: 1
    }}
}}

quorum {{
    provider: corosync_votequorum
    two_node: 1
}}

logging {{
    to_syslog: yes
    syslog_facility: daemon
    debug: off
}}"""

            # Write config
            conf_path = "/etc/corosync/corosync.conf"
            os.makedirs(os.path.dirname(conf_path), exist_ok=True)

            try:
                with open(conf_path, "w") as f:
                    f.write(corosync_conf)
            except PermissionError:
                return {"success": False, "error": "Permission denied. Run as root."}

            # Start corosync
            r = subprocess.run(
                "systemctl enable --now corosync 2>/dev/null && "
                "systemctl enable --now pacemaker 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )

            return {
                "success": r.returncode == 0,
                "error": r.stderr.strip() if r.returncode != 0 else "",
                "cluster_name": cluster_name,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def join_cluster(self, remote_host: str, cluster_name: str = "nexve") -> dict:
        """Join an existing cluster."""
        try:
            # Check if already clustered
            check = subprocess.run(
                "corosync-cfgtool -s 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if "Ring ID" in check.stdout:
                return {"success": False, "error": "Node is already part of a cluster"}

            # Copy corosync config from existing node
            r = subprocess.run(
                f"scp {remote_host}:/etc/corosync/corosync.conf /etc/corosync/corosync.conf 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                return {"success": False, "error": f"Failed to copy config: {r.stderr.strip()}"}

            # Start services
            r2 = subprocess.run(
                "systemctl enable --now corosync 2>/dev/null && "
                "systemctl enable --now pacemaker 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )

            return {
                "success": r2.returncode == 0,
                "error": r2.stderr.strip() if r2.returncode != 0 else "",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_node(self, node_name: str) -> dict:
        """Remove a node from the cluster."""
        try:
            r = subprocess.run(
                f"pcs node remove {node_name} 2>/dev/null || "
                f"corosync-cfgtool -R 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return {"success": r.returncode == 0, "error": r.stderr.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def destroy_cluster(self) -> dict:
        """Destroy the local cluster."""
        try:
            commands = [
                "systemctl stop corosync 2>/dev/null",
                "systemctl stop pacemaker 2>/dev/null",
                "systemctl disable corosync 2>/dev/null",
                "systemctl disable pacemaker 2>/dev/null",
                "rm -f /etc/corosync/corosync.conf 2>/dev/null",
            ]
            for cmd in commands:
                subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    def generate_join_token(self, node_name: str) -> dict:
        """Generate a join token for a new node."""
        import secrets
        import hashlib
        import time

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Store token in a temporary file
        token_dir = "/var/lib/nexve/cluster"
        os.makedirs(token_dir, exist_ok=True)
        token_file = f"{token_dir}/join_tokens.json"

        tokens = {}
        if os.path.exists(token_file):
            try:
                with open(token_file) as f:
                    tokens = json.load(f)
            except Exception:
                tokens = {}

        tokens[token_hash] = {
            "node_name": node_name,
            "created": time.time(),
            "expires": time.time() + 3600,  # 1 hour
            "used": False,
        }

        with open(token_file, "w") as f:
            json.dump(tokens, f, indent=2)

        return {
            "success": True,
            "token": token,
            "node_name": node_name,
            "expires_in": 3600,
        }

    def validate_join_token(self, token: str) -> dict:
        """Validate a join token."""
        import hashlib
        import time

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_file = "/var/lib/nexve/cluster/join_tokens.json"

        if not os.path.exists(token_file):
            return {"valid": False, "error": "No tokens found"}

        try:
            with open(token_file) as f:
                tokens = json.load(f)

            if token_hash not in tokens:
                return {"valid": False, "error": "Invalid token"}

            t = tokens[token_hash]
            if t.get("used", False):
                return {"valid": False, "error": "Token already used"}
            if time.time() > t.get("expires", 0):
                return {"valid": False, "error": "Token expired"}

            return {
                "valid": True,
                "node_name": t["node_name"],
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def get_cluster_config(self) -> dict:
        """Get the current cluster configuration."""
        conf_path = "/etc/corosync/corosync.conf"
        if not os.path.exists(conf_path):
            return {"exists": False}

        try:
            with open(conf_path) as f:
                conf = f.read()
            return {"exists": True, "config": conf}
        except Exception as e:
            return {"exists": False, "error": str(e)}

    # ── pmxcfs (Proxmox Cluster File System) ──

    def _has_pmxcfs(self) -> bool:
        """Check if pmxcfs is available."""
        r = subprocess.run("which pmxcfs 2>/dev/null || ls /usr/lib/pmxcfs 2>/dev/null",
                          shell=True, capture_output=True, text=True, timeout=5)
        return r.returncode == 0

    def pmxcfs_status(self) -> dict:
        """Get pmxcfs status."""
        r = subprocess.run("systemctl is-active pmxcfs 2>/dev/null",
                          shell=True, capture_output=True, text=True, timeout=5)
        running = r.stdout.strip() == "active"
        # Check if cluster filesystem is mounted
        mr = subprocess.run("mount | grep /etc/pve 2>/dev/null",
                           shell=True, capture_output=True, text=True, timeout=5)
        mounted = "/etc/pve" in mr.stdout
        return {
            "available": self._has_pmxcfs(),
            "running": running,
            "mounted": mounted,
            "mountpoint": "/etc/pve",
        }

    def pmxcfs_read(self, path: str) -> dict:
        """Read a file from the cluster filesystem (/etc/pve)."""
        full_path = f"/etc/pve/{path.lstrip('/')}"
        if not os.path.exists(full_path):
            return {"success": False, "error": "File not found"}
        try:
            with open(full_path) as f:
                content = f.read()
            return {"success": True, "path": path, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pmxcfs_write(self, path: str, content: str) -> dict:
        """Write a file to the cluster filesystem (/etc/pve)."""
        full_path = f"/etc/pve/{path.lstrip('/')}"
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            return {"success": True, "path": path}
        except PermissionError:
            return {"success": False, "error": "Permission denied. Requires cluster admin."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pmxcfs_list(self, path: str = "") -> dict:
        """List files/dirs in the cluster filesystem."""
        full_path = f"/etc/pve/{path.lstrip('/')}/" if path else "/etc/pve/"
        try:
            entries = []
            if os.path.exists(full_path):
                for entry in sorted(os.listdir(full_path)):
                    entry_path = f"{path}/{entry}" if path else entry
                    is_dir = os.path.isdir(os.path.join(full_path, entry))
                    entries.append({"name": entry, "path": entry_path, "type": "dir" if is_dir else "file"})
            return {"success": True, "entries": entries}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def pmxcfs_delete(self, path: str) -> dict:
        """Delete a file from the cluster filesystem."""
        full_path = f"/etc/pve/{path.lstrip('/')}"
        try:
            if os.path.isdir(full_path):
                os.rmdir(full_path)
            else:
                os.remove(full_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Watchdog Fencing ──

    def watchdog_status(self) -> dict:
        """Get watchdog status."""
        r = subprocess.run("lsmod | grep softdog 2>/dev/null || echo ''",
                          shell=True, capture_output=True, text=True, timeout=5)
        loaded = "softdog" in r.stdout
        # Check watchdog device
        wr = subprocess.run("ls -la /dev/watchdog 2>/dev/null || echo ''",
                           shell=True, capture_output=True, text=True, timeout=5)
        device_exists = "/dev/watchdog" in wr.stdout
        # Check pacemaker watchdog config
        pr = subprocess.run("crm configure show 2>/dev/null | grep watchdog || echo ''",
                          shell=True, capture_output=True, timeout=5)
        pacemaker_configured = "watchdog" in (pr.stdout or "").lower()
        return {
            "loaded": loaded,
            "device_exists": device_exists,
            "pacemaker_configured": pacemaker_configured,
            "module": "softdog",
        }

    def watchdog_enable(self) -> dict:
        """Enable hardware watchdog for fencing."""
        commands = [
            "modprobe softdog 2>/dev/null",
            "chmod 600 /dev/watchdog 2>/dev/null",
            # Persist across reboots
            "echo softdog > /etc/modules-load.d/watchdog.conf 2>/dev/null",
        ]
        for cmd in commands:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        # Configure pacemaker to use watchdog
        subprocess.run(
            "crm configure property watchdog-timeout=30s 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=10
        )
        return self.watchdog_status()

    def watchdog_disable(self) -> dict:
        """Disable hardware watchdog."""
        subprocess.run("rm -f /etc/modules-load.d/watchdog.conf 2>/dev/null",
                      shell=True, capture_output=True, timeout=5)
        subprocess.run("rmmod softdog 2>/dev/null", shell=True, capture_output=True, timeout=5)
        return self.watchdog_status()

    # ── Multi-master ──

    def get_multi_master_status(self) -> dict:
        """Check multi-master cluster status."""
        nodes = self.get_nodes()
        online = [n for n in nodes if n.get("status") == "online"]
        # Get resource status
        r = subprocess.run("crm status 2>/dev/null || echo ''",
                          shell=True, capture_output=True, text=True, timeout=10)
        resources = []
        if r.stdout:
            for line in r.stdout.splitlines():
                line = line.strip()
                if "Started" in line or "Stopped" in line or "Failed" in line:
                    resources.append(line)
        return {
            "total_nodes": len(nodes),
            "online_nodes": len(online),
            "nodes": nodes,
            "resources": resources,
            "quorate": len(online) > len(nodes) // 2,
        }

    def get_node_resources(self, node_name: str) -> dict:
        """Get resources running on a specific node."""
        r = subprocess.run(
            f"crm status 2>/dev/null | grep -A50 'Full List' || echo ''",
            shell=True, capture_output=True, text=True, timeout=10
        )
        resources = []
        for line in r.stdout.splitlines():
            if node_name in line or "Started" in line:
                resources.append(line.strip())
        return {"node": node_name, "resources": resources}
