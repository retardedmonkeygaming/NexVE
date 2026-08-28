import subprocess
import json
from typing import List
from sqlalchemy.orm import Session as DBSession
from ..models.firewall import FirewallRule, FirewallGroup


class FirewallService:
    def run_cmd(self, cmd: str) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Timeout"}

    def apply_rules(self, db: DBSession, target_type: str, target_id: str):
        """Generate and apply nftables ruleset for a target."""
        rules = db.query(FirewallRule).filter(
            FirewallRule.target_type == target_type,
            FirewallRule.target_id == target_id,
            FirewallRule.enabled == True
        ).order_by(FirewallRule.position).all()

        if target_type == "host":
            chain = "nexve-host"
            self.run_cmd(f"nft add table inet nexve 2>/dev/null || true")
            self.run_cmd(f"nft flush chain inet nexve {chain} 2>/dev/null || true")
        else:
            chain = f"nexve-{target_type}-{target_id}"
            self.run_cmd(f"nft add table inet nexve 2>/dev/null || true")
            self.run_cmd(f"nft add chain inet nexve {chain} 2>/dev/null || true")
            self.run_cmd(f"nft flush chain inet nexve {chain}")

        for rule in rules:
            nft = self._build_nft_rule(rule)
            if nft:
                self.run_cmd(f"nft add rule inet nexve {chain} {nft}")

        return {"success": True, "rules_applied": len(rules)}

    def _build_nft_rule(self, rule: FirewallRule) -> str:
        parts = []
        if rule.direction == "in":
            parts.append("iifname \"*\"")
        else:
            parts.append("oifname \"*\"")
        if rule.protocol and rule.protocol != "all":
            parts.append(f"ip protocol {rule.protocol}")
        if rule.source:
            parts.append(f"ip saddr {rule.source}")
        if rule.destination:
            parts.append(f"ip daddr {rule.destination}")
        if rule.sport:
            parts.append(f"th sport {rule.sport}")
        if rule.dport:
            parts.append(f"th dport {rule.dport}")

        match = " ".join(parts)
        action = rule.action
        if rule.log:
            action = f"log prefix \"[{rule.comment or 'NexVE'}]\" {action}"
        return f"{match} {action}" if match else f"{action}"


    # ── Firewall Macros (predefined service groups) ──

    MACROS = {
        "ssh": {"protocol": "tcp", "dport": "22", "description": "SSH (Secure Shell)"},
        "http": {"protocol": "tcp", "dport": "80", "description": "HTTP (Web Server)"},
        "https": {"protocol": "tcp", "dport": "443", "description": "HTTPS (Secure Web)"},
        "web": {"protocol": "tcp", "dport": "80,443", "description": "Web (HTTP + HTTPS)"},
        "dns": {"protocol": "udp", "dport": "53", "description": "DNS"},
        "ftp": {"protocol": "tcp", "dport": "21", "description": "FTP"},
        "smtp": {"protocol": "tcp", "dport": "25", "description": "SMTP (Email)"},
        "mysql": {"protocol": "tcp", "dport": "3306", "description": "MySQL/MariaDB"},
        "postgresql": {"protocol": "tcp", "dport": "5432", "description": "PostgreSQL"},
        "mongodb": {"protocol": "tcp", "dport": "27017", "description": "MongoDB"},
        "redis": {"protocol": "tcp", "dport": "6379", "description": "Redis"},
        "docker": {"protocol": "tcp", "dport": "2375,2376", "description": "Docker API"},
        "kubernetes": {"protocol": "tcp", "dport": "6443", "description": "Kubernetes API"},
        "rdp": {"protocol": "tcp", "dport": "3389", "description": "RDP (Remote Desktop)"},
        "vnc": {"protocol": "tcp", "dport": "5900-5910", "description": "VNC"},
        "smtps": {"protocol": "tcp", "dport": "465", "description": "SMTPS (Secure Email)"},
        "submission": {"protocol": "tcp", "dport": "587", "description": "SMTP Submission"},
        "imap": {"protocol": "tcp", "dport": "143", "description": "IMAP"},
        "imaps": {"protocol": "tcp", "dport": "993", "description": "IMAPS (Secure IMAP)"},
        "pop3": {"protocol": "tcp", "dport": "110", "description": "POP3"},
        "pop3s": {"protocol": "tcp", "dport": "995", "description": "POP3S (Secure POP3)"},
        "ntp": {"protocol": "udp", "dport": "123", "description": "NTP (Time Sync)"},
        "syslog": {"protocol": "udp", "dport": "514", "description": "Syslog"},
        "snmp": {"protocol": "udp", "dport": "161", "description": "SNMP"},
        "ldap": {"protocol": "tcp", "dport": "389", "description": "LDAP"},
        "ldaps": {"protocol": "tcp", "dport": "636", "description": "LDAPS (Secure LDAP)"},
        "icmp": {"protocol": "icmp", "dport": "", "description": "ICMP (Ping)"},
    }

    def get_macros(self) -> dict:
        """Return predefined firewall macros."""
        return {"macros": self.MACROS}

    def apply_macro(self, macro_name: str, direction: str = "in", action: str = "accept") -> dict:
        """Apply a firewall macro (predefined rule)."""
        if macro_name not in self.MACROS:
            return {"success": False, "error": f"Unknown macro: {macro_name}"}
        macro = self.MACROS[macro_name]
        parts = []
        if direction == "in":
            parts.append("iifname \"*\"")
        else:
            parts.append("oifname \"*\"")
        if macro["protocol"] and macro["protocol"] != "all":
            parts.append(f"ip protocol {macro['protocol']}")
        if macro["dport"]:
            parts.append(f"th dport {macro['dport']}")
        match = " ".join(parts)
        nft_rule = f"{match} {action}"
        chain = "nexve-host"
        self.run_cmd(f"nft add table inet nexve 2>/dev/null || true")
        self.run_cmd(f"nft add chain inet nexve {chain} 2>/dev/null || true")
        self.run_cmd(f"nft add rule inet nexve {chain} {nft_rule}")
        return {"success": True, "macro": macro_name, "rule": nft_rule}

    # ── Per-VM Firewall ──

    def apply_vm_firewall(self, vm_name: str, rules: List[dict]) -> dict:
        """Apply firewall rules for a specific VM via nftables."""
        chain = f"nexve-vm-{vm_name}"
        self.run_cmd("nft add table inet nexve 2>/dev/null || true")
        self.run_cmd(f"nft add chain inet nexve {chain} 2>/dev/null || true")
        self.run_cmd(f"nft flush chain inet nexve {chain}")

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            nft = self._build_nft_rule_from_dict(rule)
            if nft:
                self.run_cmd(f"nft add rule inet nexve {chain} {nft}")

        # Hook into forward chain for this VM's traffic
        # (simplified — in production you'd match by MAC/IP)
        return {"success": True, "rules_applied": len(rules)}

    def _build_nft_rule_from_dict(self, rule: dict) -> str:
        """Build nftables rule from a dict."""
        parts = []
        direction = rule.get("direction", "in")
        if direction == "in":
            parts.append("iifname \"*\"")
        else:
            parts.append("oifname \"*\"")
        if rule.get("protocol") and rule["protocol"] != "all":
            parts.append(f"ip protocol {rule['protocol']}")
        if rule.get("source"):
            parts.append(f"ip saddr {rule['source']}")
        if rule.get("destination"):
            parts.append(f"ip daddr {rule['destination']}")
        if rule.get("sport"):
            parts.append(f"th sport {rule['sport']}")
        if rule.get("dport"):
            parts.append(f"th dport {rule['dport']}")
        match = " ".join(parts)
        action = rule.get("action", "accept")
        if rule.get("log"):
            action = f'log prefix "[{rule.get("comment", "NexVE")}]" {action}'
        return f"{match} {action}" if match else action

    # ── Connection Tracking ──

    def get_connections(self) -> List[dict]:
        """Get active firewall connections from nftables."""
        r = self.run_cmd("nft list connections 2>/dev/null || conntrack -L 2>/dev/null || echo ''")
        connections = []
        if r["success"] and r["stdout"]:
            for line in r["stdout"].splitlines()[:100]:  # Limit to 100
                connections.append({"info": line.strip()})
        return connections

    def get_stats(self) -> dict:
        r = self.run_cmd("nft list ruleset -j 2>/dev/null || echo '{\"rules\":[]}'")
        try:
            return json.loads(r["stdout"]) if r["success"] else {"rules": []}
        except json.JSONDecodeError:
            return {"rules": []}
