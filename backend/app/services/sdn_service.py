"""
NexVE SDN Service
Manages Software-Defined Networking zones, VNets, and VXLAN tunneling.
"""
import subprocess
from typing import List
import json


class SDNService:
    """Manages Software-Defined Networking."""

    def get_sdn_status(self) -> dict:
        """Get SDN overall status."""
        try:
            # Check if SDN is available
            r = subprocess.run(
                "which sdn 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            sdn_available = r.returncode == 0 and r.stdout.strip() != ""

            # Check network namespace for SDN
            ns_r = subprocess.run(
                "ip netns list 2>/dev/null | grep sdn || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )

            return {
                "available": sdn_available,
                "namespaces": ns_r.stdout.strip().splitlines() if ns_r.stdout.strip() else [],
            }
        except Exception:
            return {"available": False, "namespaces": []}

    def list_zones(self) -> List[dict]:
        """List SDN zones."""
        try:
            r = subprocess.run(
                "cat /etc/network/interfaces.d/sdn 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            zones = []
            if r.stdout.strip():
                for line in r.stdout.splitlines():
                    if "auto" in line and "zone" in line:
                        name = line.split()[-1] if len(line.split()) > 1 else ""
                        zones.append({"name": name, "type": "simple"})
            return zones
        except Exception:
            return []

    def create_zone(self, name: str, zone_type: str = "simple", 
                   bridge: str = "", mtu: int = 1500) -> dict:
        """Create an SDN zone."""
        try:
            # Create bridge for the zone
            bridge_name = bridge or f"vz{mtu}"

            # Add to network config
            config = f"""
auto {bridge_name}
iface {bridge_name} inet manual
    bridge-ports none
    bridge-stp off
    bridge-fd 0
"""
            # Write to interfaces.d
            try:
                with open(f"/etc/network/interfaces.d/sdn-{name}", "w") as f:
                    f.write(config)
            except PermissionError:
                return {"success": False, "error": "Permission denied"}

            # Bring up bridge
            r = subprocess.run(
                f"ip link add {bridge_name} type bridge 2>/dev/null && "
                f"ip link set {bridge_name} up 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=10
            )

            return {
                "success": True,
                "zone": name,
                "bridge": bridge_name,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_zone(self, name: str) -> dict:
        """Delete an SDN zone."""
        try:
            bridge_name = f"vz{name}"

            # Delete bridge
            subprocess.run(
                f"ip link set {bridge_name} down 2>/dev/null && "
                f"ip link del {bridge_name} 2>/dev/null",
                shell=True, capture_output=True, timeout=10
            )

            # Remove config
            subprocess.run(
                f"rm -f /etc/network/interfaces.d/sdn-{name}",
                shell=True, capture_output=True, timeout=5
            )

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_vnets(self) -> List[dict]:
        """List virtual networks."""
        try:
            # Check for VXLAN interfaces
            r = subprocess.run(
                "ip -d link show type vxlan 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True, timeout=5
            )
            vnets = []
            if r.stdout.strip():
                for line in r.stdout.splitlines():
                    if "vxlan" in line.lower():
                        parts = line.split()
                        name = parts[1].rstrip(":") if len(parts) > 1 else ""
                        vnets.append({"name": name, "type": "vxlan"})
            return vnets
        except Exception:
            return []

    def create_vnet(self, name: str, zone_name: str = "", 
                   vlan_id: int = 0, cidr: str = "",
                   gateway: str = "") -> dict:
        """Create a virtual network (VXLAN or VLAN)."""
        try:
            vxlan_id = vlan_id or hash(name) % 16777216
            port = 4789

            # Create VXLAN interface
            r = subprocess.run(
                f"ip link add {name} type vxlan id {vxlan_id} dstport {port}",
                shell=True, capture_output=True, text=True, timeout=10
            )

            if r.returncode != 0:
                return {"success": False, "error": r.stderr.strip()}

            # Create bridge and add VXLAN to it
            bridge_name = f"br-{name}"
            subprocess.run(
                f"ip link add {bridge_name} type bridge 2>/dev/null && "
                f"ip link set {name} master {bridge_name} 2>/dev/null && "
                f"ip link set {name} up 2>/dev/null && "
                f"ip link set {bridge_name} up 2>/dev/null",
                shell=True, capture_output=True, timeout=10
            )

            # Assign IP if CIDR provided
            if cidr:
                subprocess.run(
                    f"ip addr add {cidr} dev {bridge_name} 2>/dev/null",
                    shell=True, capture_output=True, timeout=5
                )

            return {
                "success": True,
                "vnet": name,
                "vxlan_id": vxlan_id,
                "bridge": bridge_name,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_vnet(self, name: str) -> dict:
        """Delete a virtual network."""
        try:
            bridge_name = f"br-{name}"
            subprocess.run(
                f"ip link set {name} down 2>/dev/null && "
                f"ip link del {name} 2>/dev/null && "
                f"ip link set {bridge_name} down 2>/dev/null && "
                f"ip link del {bridge_name} 2>/dev/null",
                shell=True, capture_output=True, timeout=10
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_sdn(self) -> dict:
        """Apply SDN configuration (restart all zones/vnets)."""
        try:
            r = subprocess.run(
                "systemctl restart networking 2>/dev/null || true",
                shell=True, capture_output=True, text=True, timeout=30
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
