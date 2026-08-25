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

    def get_stats(self) -> dict:
        r = self.run_cmd("nft list ruleset -j 2>/dev/null || echo '{\"rules\":[]}'")
        try:
            return json.loads(r["stdout"]) if r["success"] else {"rules": []}
        except json.JSONDecodeError:
            return {"rules": []}
