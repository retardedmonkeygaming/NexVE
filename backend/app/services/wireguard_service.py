"""
NexVE WireGuard VPN Service
Manages WireGuard interfaces, peers, and tunnels.
"""
import subprocess
import json
import os
import re
from typing import List, Optional


class WireGuardService:
    """Manages WireGuard VPN interfaces and peers."""

    def run_cmd(self, cmd: str, timeout: int = 15) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out"}
        except Exception:
            return {"success": False, "stdout": "", "stderr": "Command not available"}

    def is_available(self) -> bool:
        """Check if WireGuard is installed."""
        r = self.run_cmd("which wg 2>/dev/null && wg --version 2>/dev/null")
        return r["success"]

    def list_interfaces(self) -> List[dict]:
        """List all WireGuard interfaces."""
        r = self.run_cmd("wg show all dump 2>/dev/null")
        if not r["success"] or not r["stdout"]:
            return []
        
        interfaces = []
        current_iface = None
        
        for line in r["stdout"].splitlines():
            parts = line.split("\t")
            if len(parts) >= 4 and parts[0] and not parts[0].startswith("\t"):
                # Interface line: name public_key listen_port fwmark
                current_iface = {
                    "name": parts[0],
                    "public_key": parts[1],
                    "listen_port": int(parts[2]) if parts[2] != "0" else None,
                    "peers": [],
                }
                interfaces.append(current_iface)
            elif len(parts) >= 5 and current_iface:
                # Peer line: public_key preshared_key endpoint allowed_ips latest_handshake transfer_rx transfer_tx persistent_keepalive
                peer = {
                    "public_key": parts[0],
                    "preshared_key": parts[1] if parts[1] != "(none)" else None,
                    "endpoint": parts[2] if parts[2] != "(none)" else None,
                    "allowed_ips": parts[3].split(",") if parts[3] != "(none)" else [],
                    "latest_handshake": int(parts[4]) if parts[4] and parts[4] != "0" else None,
                    "transfer_rx": int(parts[5]) if len(parts) > 5 and parts[5] else 0,
                    "transfer_tx": int(parts[6]) if len(parts) > 6 and parts[6] else 0,
                    "persistent_keepalive": int(parts[7]) if len(parts) > 7 and parts[7] not in ("0", "(none)") else None,
                }
                current_iface["peers"].append(peer)
        
        return interfaces

    def get_interface(self, name: str) -> Optional[dict]:
        """Get a specific WireGuard interface."""
        ifaces = self.list_interfaces()
        for iface in ifaces:
            if iface["name"] == name:
                return iface
        return None

    def create_interface(self, name: str, listen_port: int = 51820, address: str = "") -> dict:
        """Create and configure a WireGuard interface."""
        # Generate keys
        privkey_r = self.run_cmd("wg genkey")
        if not privkey_r["success"]:
            return {"success": False, "error": "Failed to generate private key"}
        private_key = privkey_r["stdout"]
        
        pubkey_r = self.run_cmd(f"echo '{private_key}' | wg pubkey")
        if not pubkey_r["success"]:
            return {"success": False, "error": "Failed to generate public key"}
        public_key = pubkey_r["stdout"]

        # Create the interface
        r = self.run_cmd(f"ip link add {name} type wireguard")
        if not r["success"] and "EEXIST" not in r.get("stderr", ""):
            return {"success": False, "error": f"Failed to create interface: {r['stderr']}"}

        # Set listen port
        self.run_cmd(f"wg set {name} listen-port {listen_port} private-key <(echo '{private_key}')")

        # Set address if provided
        if address:
            self.run_cmd(f"ip addr add {address} dev {name}")

        # Bring up
        self.run_cmd(f"ip link set {name} up")

        return {
            "success": True,
            "name": name,
            "private_key": private_key,
            "public_key": public_key,
            "listen_port": listen_port,
            "address": address,
        }

    def delete_interface(self, name: str) -> dict:
        """Delete a WireGuard interface."""
        self.run_cmd(f"wg set {name} peer none 2>/dev/null")
        return self.run_cmd(f"ip link del {name}")

    def set_interface(self, name: str, listen_port: int = None, private_key: str = None) -> dict:
        """Update interface configuration."""
        cmd = f"wg set {name}"
        if listen_port:
            cmd += f" listen-port {listen_port}"
        if private_key:
            cmd += f" private-key <(echo '{private_key}')"
        return self.run_cmd(cmd)

    def add_peer(self, interface: str, public_key: str, endpoint: str = "",
                 allowed_ips: str = "0.0.0.0/0", keepalive: int = 0,
                 preshared_key: str = "") -> dict:
        """Add a peer to a WireGuard interface."""
        cmd = f"wg set {interface} peer {public_key}"
        if endpoint:
            cmd += f" endpoint {endpoint}"
        cmd += f" allowed-ips {allowed_ips}"
        if keepalive > 0:
            cmd += f" persistent-keepalive {keepalive}"
        if preshared_key:
            cmd += f" preshared-key <(echo '{preshared_key}')"
        return self.run_cmd(cmd)

    def remove_peer(self, interface: str, public_key: str) -> dict:
        """Remove a peer from a WireGuard interface."""
        return self.run_cmd(f"wg set {interface} peer {public_key} remove")

    def generate_key(self) -> dict:
        """Generate a new WireGuard key pair."""
        privkey_r = self.run_cmd("wg genkey")
        if not privkey_r["success"]:
            return {"success": False, "error": "Failed to generate key"}
        private_key = privkey_r["stdout"]
        
        pubkey_r = self.run_cmd(f"echo '{private_key}' | wg pubkey")
        if not pubkey_r["success"]:
            return {"success": False, "error": "Failed to derive public key"}
        
        psk_r = self.run_cmd("wg genpsk")
        preshared_key = psk_r["stdout"] if psk_r["success"] else None
        
        return {
            "success": True,
            "private_key": private_key,
            "public_key": pubkey_r["stdout"],
            "preshared_key": preshared_key,
        }

    def get_config(self, name: str) -> str:
        """Get WireGuard configuration in standard .conf format."""
        iface = self.get_interface(name)
        if not iface:
            return ""

        lines = [f"[Interface]"]
        if iface.get("listen_port"):
            lines.append(f"ListenPort = {iface['listen_port']}")
        lines.append(f"# Public Key = {iface['public_key']}")
        lines.append("")

        for peer in iface.get("peers", []):
            lines.append("[Peer]")
            lines.append(f"PublicKey = {peer['public_key']}")
            if peer.get("preshared_key"):
                lines.append(f"PresharedKey = {peer['preshared_key']}")
            if peer.get("endpoint"):
                lines.append(f"Endpoint = {peer['endpoint']}")
            if peer.get("allowed_ips"):
                lines.append(f"AllowedIPs = {', '.join(peer['allowed_ips'])}")
            if peer.get("persistent_keepalive"):
                lines.append(f"PersistentKeepalive = {peer['persistent_keepalive']}")
            lines.append("")

        return "\n".join(lines)

    def get_traffic_stats(self) -> dict:
        """Get aggregate traffic stats across all interfaces."""
        ifaces = self.list_interfaces()
        total_rx = 0
        total_tx = 0
        total_peers = 0
        for iface in ifaces:
            for peer in iface.get("peers", []):
                total_rx += peer.get("transfer_rx", 0)
                total_tx += peer.get("transfer_tx", 0)
                total_peers += 1
        return {
            "total_rx_bytes": total_rx,
            "total_tx_bytes": total_tx,
            "total_peers": total_peers,
            "interfaces": len(ifaces),
        }
