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
