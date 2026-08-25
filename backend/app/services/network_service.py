import subprocess
import json
import os
from typing import List


class NetworkService:
    def run_cmd(self, cmd: str) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Timeout"}

    # ── Bridges ──

    def list_bridges(self) -> List[dict]:
        bridges = []
        # Parse from ip command
        r = self.run_cmd("ip -j link show type bridge")
        if r["success"]:
            try:
                data = json.loads(r["stdout"])
                for br in data:
                    ifname = br.get("ifname", "")
                    operstate = br.get("operstate", "unknown")
                    mac = br.get("address", "")
                    # Get IPs on this bridge
                    ip_r = self.run_cmd(f"ip -4 addr show dev {ifname}")
                    ips = []
                    for line in ip_r["stdout"].splitlines():
                        line = line.strip()
                        if line.startswith("inet "):
                            ips.append(line.split()[1])
                    # Get STP status
                    stp_r = self.run_cmd(f"cat /sys/class/net/{ifname}/bridge/stp_state 2>/dev/null")
                    stp = "enabled" if stp_r["stdout"].strip() == "1" else "disabled"
                    # Get member interfaces
                    mbr_r = self.run_cmd(f"bridge link show master {ifname}")
                    members = []
                    for line in mbr_r["stdout"].splitlines():
                        if "master" in line and ifname in line:
                            parts = line.split()
                            if parts:
                                members.append(parts[1].rstrip(":"))
                    bridges.append({
                        "name": ifname,
                        "state": operstate,
                        "mac": mac,
                        "ips": ips,
                        "stp": stp,
                        "members": members,
                    })
            except json.JSONDecodeError:
                pass
        return bridges

    def create_bridge(self, name: str) -> dict:
        r = self.run_cmd(f"ip link add name {name} type bridge")
        if r["success"]:
            self.run_cmd(f"ip link set {name} up")
        return r

    def delete_bridge(self, name: str) -> dict:
        self.run_cmd(f"ip link set {name} down")
        return self.run_cmd(f"ip link del {name}")

    def add_port(self, bridge: str, iface: str) -> dict:
        self.run_cmd(f"ip link set {iface} down")
        r = self.run_cmd(f"ip link set {iface} master {bridge}")
        self.run_cmd(f"ip link set {iface} up")
        return r

    def remove_port(self, iface: str) -> dict:
        self.run_cmd(f"ip link set {iface} down")
        r = self.run_cmd(f"ip link set {iface} nomaster")
        self.run_cmd(f"ip link set {iface} up")
        return r

    def set_bridge_ip(self, bridge: str, cidr: str) -> dict:
        self.run_cmd(f"ip addr flush dev {bridge}")
        return self.run_cmd(f"ip addr add {cidr} dev {bridge}")

    # ── VLANs ──

    def list_vlans(self) -> List[dict]:
        r = self.run_cmd("ip -j -d link show type vlan")
        vlans = []
        if r["success"]:
            try:
                data = json.loads(r["stdout"])
                for v in data:
                    info = v.get("linkinfo", {})
                    vlans.append({
                        "name": v.get("ifname"),
                        "vlan_id": info.get("vlan_id"),
                        "parent": info.get("link"),
                        "state": v.get("operstate", "unknown"),
                    })
            except json.JSONDecodeError:
                pass
        return vlans

    def create_vlan(self, parent: str, vlan_id: int, name: str = "") -> dict:
        if not name:
            name = f"{parent}.{vlan_id}"
        r = self.run_cmd(f"ip link add link {parent} name {name} type vlan id {vlan_id}")
        if r["success"]:
            self.run_cmd(f"ip link set {name} up")
        return r

    def delete_vlan(self, name: str) -> dict:
        self.run_cmd(f"ip link set {name} down")
        return self.run_cmd(f"ip link del {name}")

    # ── Bonding ──

    def list_bonds(self) -> List[dict]:
        bonds = []
        r = self.run_cmd("ip -j link show type bond")
        if r["success"]:
            try:
                data = json.loads(r["stdout"])
                for b in data:
                    name = b.get("ifname", "")
                    # Get bond mode
                    mode_r = self.run_cmd(f"cat /sys/class/net/{name}/bonding/mode 2>/dev/null")
                    mode = mode_r["stdout"].split()[0] if mode_r["success"] else "unknown"
                    # Get slave interfaces
                    sl_r = self.run_cmd(f"cat /sys/class/net/{name}/bonding/slaves 2>/dev/null")
                    slaves = sl_r["stdout"].split() if sl_r["success"] else []
                    # Get IPs
                    ip_r = self.run_cmd(f"ip -4 addr show dev {name}")
                    ips = []
                    for line in ip_r["stdout"].splitlines():
                        if line.strip().startswith("inet "):
                            ips.append(line.strip().split()[1])
                    bonds.append({
                        "name": name,
                        "mode": mode,
                        "state": b.get("operstate", "unknown"),
                        "slaves": slaves,
                        "ips": ips,
                    })
            except json.JSONDecodeError:
                pass
        return bonds

    def create_bond(self, name: str, mode: str, slaves: List[str]) -> dict:
        self.run_cmd(f"ip link add name {name} type bond mode {mode}")
        for slave in slaves:
            self.run_cmd(f"ip link set {slave} down")
            self.run_cmd(f"ip link set {slave} master {name}")
            self.run_cmd(f"ip link set {slave} up")
        self.run_cmd(f"ip link set {name} up")
        return {"success": True, "stdout": f"Bond {name} created", "stderr": ""}

    def delete_bond(self, name: str) -> dict:
        self.run_cmd(f"ip link set {name} down")
        return self.run_cmd(f"ip link del {name}")

    # ── Firewall (nftables) ──

    def firewall_rules(self) -> dict:
        r = self.run_cmd("nft list ruleset")
        return {"success": r["success"], "rules": r["stdout"] if r["success"] else ""}

    def firewall_add_rule(self, rule: str) -> dict:
        return self.run_cmd(f"nft add rule {rule}")

    def firewall_delete_rule(self, handle: int, table: str = "inet", chain: str = "forward") -> dict:
        return self.run_cmd(f"nft delete rule {table} {chain} handle {handle}")

    def firewall_enable(self) -> dict:
        return self.run_cmd("systemctl enable --now nftables")

    def firewall_disable(self) -> dict:
        return self.run_cmd("systemctl stop nftables")

    def firewall_set_policy(self, chain: str, policy: str) -> dict:
        return self.run_cmd(f"nft add chain inet nexve {chain} {{ policy {policy}; }}")

    # ── Interfaces overview ──

    def list_interfaces(self) -> List[dict]:
        r = self.run_cmd("ip -j addr")
        ifaces = []
        if r["success"]:
            try:
                data = json.loads(r["stdout"])
                for iface in data:
                    name = iface.get("ifname", "")
                    if name == "lo":
                        continue
                    ips = []
                    for addr in iface.get("addr_info", []):
                        ips.append(f"{addr.get('local')}/{addr.get('prefixlen')}")
                    ifaces.append({
                        "name": name,
                        "mac": iface.get("address", ""),
                        "state": iface.get("operstate", "unknown"),
                        "ips": ips,
                        "mtu": iface.get("mtu", 1500),
                    })
            except json.JSONDecodeError:
                pass
        return ifaces

    def get_network_overview(self) -> dict:
        return {
            "interfaces": self.list_interfaces(),
            "bridges": self.list_bridges(),
            "vlans": self.list_vlans(),
            "bonds": self.list_bonds(),
        }
