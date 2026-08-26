import subprocess
import json
import os
from typing import List


class NetworkService:
    def run_cmd(self, cmd: str, timeout: int = 30) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Timeout"}

    # ── Bridges ──

    def list_bridges(self) -> List[dict]:
        bridges = []
        r = self.run_cmd("ip -j link show type bridge")
        if r["success"]:
            try:
                data = json.loads(r["stdout"])
                for br in data:
                    ifname = br.get("ifname", "")
                    operstate = br.get("operstate", "unknown")
                    mac = br.get("address", "")
                    ip_r = self.run_cmd(f"ip -4 addr show dev {ifname}")
                    ips = []
                    for line in ip_r["stdout"].splitlines():
                        line = line.strip()
                        if line.startswith("inet "):
                            ips.append(line.split()[1])
                    stp_r = self.run_cmd(f"cat /sys/class/net/{ifname}/bridge/stp_state 2>/dev/null")
                    stp = "enabled" if stp_r["stdout"].strip() == "1" else "disabled"
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
                    mode_r = self.run_cmd(f"cat /sys/class/net/{name}/bonding/mode 2>/dev/null")
                    mode = mode_r["stdout"].split()[0] if mode_r["success"] else "unknown"
                    sl_r = self.run_cmd(f"cat /sys/class/net/{name}/bonding/slaves 2>/dev/null")
                    slaves = sl_r["stdout"].split() if sl_r["success"] else []
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

    # ── Firewall Aliases (nftables sets) ──

    def create_alias_set(self, name: str, entries: List[str], family: str = "inet") -> dict:
        """Create an nftables set (alias) with the given entries."""
        # Create the set
        r = self.run_cmd(f"nft add set {family} nexve {name} {{ type ipv4_addr; }}")
        if not r["success"] and "already" not in r.get("stderr", "").lower():
            return r

        # Add elements
        for entry in entries:
            self.run_cmd(f"nft add element {family} nexve {name} {{ {entry} }}")
        return {"success": True}

    def delete_alias_set(self, name: str, family: str = "inet") -> dict:
        return self.run_cmd(f"nft delete set {family} nexve {name}")

    def list_alias_sets(self, family: str = "inet") -> List[dict]:
        r = self.run_cmd(f"nft list table {family} nexve 2>/dev/null")
        sets = []
        if r["success"]:
            in_set = False
            current_set = None
            for line in r["stdout"].splitlines():
                if "set" in line and "{" in line and "type" in line:
                    parts = line.strip().split()
                    for i, p in enumerate(parts):
                        if p == "set" and i + 1 < len(parts):
                            current_set = parts[i + 1].rstrip(" {")
                            sets.append({"name": current_set, "entries": []})
                            in_set = True
                            break
                elif in_set and "}" in line:
                    in_set = False
                    current_set = None
                elif in_set and current_set and sets:
                    entry = line.strip().rstrip(",").rstrip(";")
                    if entry:
                        sets[-1]["entries"].append(entry)
        return sets

    # ── Security Groups (via nftables) ──

    def apply_security_group(self, group_name: str, rules: List[dict], target_interface: str = "") -> dict:
        """Apply security group rules to nftables."""
        chain = f"nexve-sg-{group_name}"
        self.run_cmd("nft add table inet nexve 2>/dev/null || true")
        self.run_cmd(f"nft add chain inet nexve {chain} 2>/dev/null || true")
        self.run_cmd(f"nft flush chain inet nexve {chain}")

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            parts = []
            direction = rule.get("direction", "in")
            if direction == "in":
                parts.append("iifname \"*\"")
            else:
                parts.append("oifname \"*\"")
            if target_interface:
                parts = [f"iifname \"{target_interface}\""] if direction == "in" else [f"oifname \"{target_interface}\""]

            protocol = rule.get("protocol", "tcp")
            if protocol and protocol != "all":
                parts.append(f"ip protocol {protocol}")
            source = rule.get("source", "")
            if source:
                parts.append(f"ip saddr {source}")
            destination = rule.get("destination", "")
            if destination:
                parts.append(f"ip daddr {destination}")
            sport = rule.get("sport", "")
            if sport:
                parts.append(f"th sport {sport}")
            dport = rule.get("dport", "")
            if dport:
                parts.append(f"th dport {dport}")

            match = " ".join(parts)
            action = rule.get("action", "accept")
            if rule.get("log"):
                action = f'log prefix "[{group_name}]" {action}'
            nft_rule = f"{match} {action}" if match else action
            self.run_cmd(f"nft add rule inet nexve {chain} {nft_rule}")

        return {"success": True, "rules_applied": len(rules)}

    def link_security_group_to_interface(self, group_name: str, iface: str, direction: str = "in") -> dict:
        """Jump to the security group chain from the forward/hook chain."""
        hook_chain = "forward" if direction == "in" else "output"
        jump_rule = f'jump nexve-sg-{group_name}'
        return self.run_cmd(f"nft add rule inet nexve {hook_chain} iifname \"{iface}\" {jump_rule}")

    # ── Rate Limiting (tc) ──

    def set_interface_rate_limit(
        self,
        iface: str,
        rx_bytes: int = None,
        tx_bytes: int = None,
        rx_burst: int = None,
        tx_burst: int = None,
    ) -> dict:
        """Set rate limits on a network interface using tc (traffic control)."""
        # Remove existing qdisc
        self.run_cmd(f"tc qdisc del dev {iface} root 2>/dev/null || true")

        # If no limits, we're done (cleared)
        if not rx_bytes and not tx_bytes:
            return {"success": True, "message": "Rate limits cleared"}

        # Root qdisc
        self.run_cmd(f"tc qdisc add dev {iface} root handle 1: prio")

        # Ingress (rx)
        if rx_bytes:
            burst = rx_burst or (rx_bytes // 10)  # default burst = 10% of rate
            self.run_cmd(f"tc qdisc add dev {iface} handle ffff: ingress")
            self.run_cmd(
                f"tc filter add dev {iface} parent ffff: protocol ip "
                f"u32 match u32 0 0 police rate {rx_bytes} burst {burst} drop flowid :1"
            )

        # Egress (tx)
        if tx_bytes:
            burst = tx_burst or (tx_bytes // 10)
            self.run_cmd(
                f"tc qdisc add dev {iface} parent 1:1 handle 10: netem rate {tx_bytes} burst {burst}"
            )

        return {"success": True}

    def get_interface_rate_limit(self, iface: str) -> dict:
        """Get current rate limit settings."""
        r = self.run_cmd(f"tc qdisc show dev {iface}")
        limits = {"iface": iface, "has_limit": False}
        if r["success"]:
            for line in r["stdout"].splitlines():
                if "rate" in line.lower() or "police" in line.lower():
                    limits["has_limit"] = True
                    limits["details"] = line.strip()
        return limits

    def clear_interface_rate_limit(self, iface: str) -> dict:
        self.run_cmd(f"tc qdisc del dev {iface} root 2>/dev/null || true")
        self.run_cmd(f"tc qdisc del dev {iface} ingress 2>/dev/null || true")
        return {"success": True}

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
