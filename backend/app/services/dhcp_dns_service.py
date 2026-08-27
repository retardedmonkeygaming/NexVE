"""
NexVE DHCP/DNS Service
Manages dnsmasq for DHCP and DNS on the host.
"""
import subprocess
import os
import re
from typing import List, Optional


class DHCPDNSService:
    """Manages DHCP and DNS via dnsmasq."""

    CONF_DIR = "/etc/dnsmasq.d"
    MAIN_CONF = "/etc/dnsmasq.conf"

    def run_cmd(self, cmd: str, timeout: int = 15) -> dict:
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return {"success": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
        except Exception:
            return {"success": False, "stdout": "", "stderr": "Command not available"}

    def is_available(self) -> bool:
        r = self.run_cmd("which dnsmasq 2>/dev/null")
        return r["success"]

    def is_running(self) -> bool:
        r = self.run_cmd("systemctl is-active dnsmasq 2>/dev/null || pgrep -x dnsmasq >/dev/null 2>&1 && echo active || echo inactive")
        return "active" in r.get("stdout", "")

    def get_status(self) -> dict:
        running = self.is_running()
        available = self.is_available()
        leases = self._count_leases()
        return {
            "running": running,
            "available": available,
            "active_leases": leases,
            "dhcp_enabled": self._check_dhcp_enabled(),
            "dns_enabled": self._check_dns_enabled(),
        }

    def _check_dhcp_enabled(self) -> bool:
        r = self.run_cmd(f"grep -r 'dhcp-range' {self.CONF_DIR}/ 2>/dev/null | grep -v '^#'")
        return bool(r["stdout"])

    def _check_dns_enabled(self) -> bool:
        r = self.run_cmd(f"grep -r 'address=' {self.CONF_DIR}/ 2>/dev/null | grep -v '^#'")
        return bool(r["stdout"]) or self._check_local_dns()

    def _check_local_dns(self) -> bool:
        r = self.run_cmd("grep 'dns=dnsmasq\\|dns-server\\|dnsmasq' /etc/NetworkManager/NetworkManager.conf 2>/dev/null")
        return bool(r["stdout"])

    def _count_leases(self) -> int:
        lease_file = "/var/lib/misc/dnsmasq.leases"
        r = self.run_cmd(f"wc -l < {lease_file} 2>/dev/null")
        try:
            return int(r["stdout"]) if r["success"] else 0
        except ValueError:
            return 0

    def list_dhcp_ranges(self) -> List[dict]:
        """List DHCP ranges from config files."""
        ranges = []
        r = self.run_cmd(f"grep -r 'dhcp-range\\|dhcp-host\\|dhcp-option' {self.CONF_DIR}/ 2>/dev/null")
        if not r["success"]:
            return ranges
        for line in r["stdout"].splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Remove filename prefix
            if ":" in line:
                line = line.split(":", 1)[1].strip()
            if line.startswith("dhcp-range="):
                parts = line[len("dhcp-range="):].split(",")
                ranges.append({
                    "type": "range",
                    "start": parts[0] if len(parts) > 0 else "",
                    "end": parts[1] if len(parts) > 1 else "",
                    "netmask": parts[2] if len(parts) > 2 else "255.255.255.0",
                    "lease_time": parts[3] if len(parts) > 3 else "24h",
                    "raw": line,
                })
            elif line.startswith("dhcp-host="):
                parts = line[len("dhcp-host="):].split(",")
                ranges.append({
                    "type": "static",
                    "mac": parts[0] if len(parts) > 0 else "",
                    "ip": parts[1] if len(parts) > 1 else "",
                    "name": parts[2] if len(parts) > 2 else "",
                    "raw": line,
                })
        return ranges

    def list_dns_records(self) -> List[dict]:
        """List DNS records from config."""
        records = []
        r = self.run_cmd(f"grep -r 'address=\\|server=\\|local=\\|domain=' {self.CONF_DIR}/ 2>/dev/null")
        if not r["success"]:
            return records
        for line in r["stdout"].splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                line = line.split(":", 1)[1].strip()
            if line.startswith("address="):
                val = line[len("address="):]
                parts = val.split("/", 1) if "/" in val else val.split(",", 1)
                records.append({
                    "type": "address",
                    "domain": parts[0].strip("/") if parts else "",
                    "ip": parts[1].strip() if len(parts) > 1 else "",
                    "raw": line,
                })
            elif line.startswith("server="):
                records.append({
                    "type": "upstream",
                    "server": line[len("server="):],
                    "raw": line,
                })
        return records

    def list_leases(self) -> List[dict]:
        """List active DHCP leases."""
        lease_file = "/var/lib/misc/dnsmasq.leases"
        r = self.run_cmd(f"cat {lease_file} 2>/dev/null")
        if not r["success"]:
            return []
        leases = []
        for line in r["stdout"].splitlines():
            parts = line.split()
            if len(parts) >= 4:
                leases.append({
                    "expires": parts[0],
                    "mac": parts[1],
                    "ip": parts[2],
                    "name": parts[3],
                    "client_id": parts[4] if len(parts) > 4 else "",
                })
        return leases

    def add_dhcp_range(self, start: str, end: str, netmask: str = "255.255.255.0",
                       lease_time: str = "24h", interface: str = "") -> dict:
        """Add a DHCP range configuration."""
        os.makedirs(self.CONF_DIR, exist_ok=True)
        conf_file = os.path.join(self.CONF_DIR, "nexve-dhcp.conf")

        entry = f"dhcp-range={start},{end},{netmask},{lease_time}"
        if interface:
            entry += f",interface={interface}"

        with open(conf_file, "a") as f:
            f.write(f"{entry}\n")

        return {"success": True, "entry": entry}

    def remove_dhcp_range(self, start: str, end: str) -> dict:
        """Remove a DHCP range from config."""
        conf_file = os.path.join(self.CONF_DIR, "nexve-dhcp.conf")
        if not os.path.exists(conf_file):
            return {"success": False, "error": "Config file not found"}

        with open(conf_file, "r") as f:
            lines = f.readlines()

        target = f"dhcp-range={start},{end}"
        with open(conf_file, "w") as f:
            for line in lines:
                if target not in line:
                    f.write(line)

        return {"success": True}

    def add_static_host(self, mac: str, ip: str, name: str = "") -> dict:
        """Add a static DHCP host reservation."""
        os.makedirs(self.CONF_DIR, exist_ok=True)
        conf_file = os.path.join(self.CONF_DIR, "nexve-dhcp.conf")

        entry = f"dhcp-host={mac},{ip}"
        if name:
            entry += f",{name}"

        with open(conf_file, "a") as f:
            f.write(f"{entry}\n")

        return {"success": True, "entry": entry}

    def add_dns_record(self, domain: str, ip: str) -> dict:
        """Add a DNS address record."""
        os.makedirs(self.CONF_DIR, exist_ok=True)
        conf_file = os.path.join(self.CONF_DIR, "nexve-dns.conf")

        entry = f"address=/{domain}/{ip}"
        with open(conf_file, "a") as f:
            f.write(f"{entry}\n")

        return {"success": True, "entry": entry}

    def remove_dns_record(self, domain: str) -> dict:
        """Remove a DNS record."""
        conf_file = os.path.join(self.CONF_DIR, "nexve-dns.conf")
        if not os.path.exists(conf_file):
            return {"success": False, "error": "Config file not found"}

        with open(conf_file, "r") as f:
            lines = f.readlines()

        target = f"address=/{domain}/"
        with open(conf_file, "w") as f:
            for line in lines:
                if target not in line:
                    f.write(line)

        return {"success": True}

    def add_upstream_dns(self, server: str) -> dict:
        """Add an upstream DNS server."""
        os.makedirs(self.CONF_DIR, exist_ok=True)
        conf_file = os.path.join(self.CONF_DIR, "nexve-dns.conf")

        with open(conf_file, "a") as f:
            f.write(f"server={server}\n")

        return {"success": True}

    def restart(self) -> dict:
        """Restart dnsmasq."""
        return self.run_cmd("systemctl restart dnsmasq 2>/dev/null || service dnsmasq restart 2>/dev/null || killall -HUP dnsmasq")

    def get_config_content(self) -> str:
        """Get the full dnsmasq configuration."""
        configs = []
        # Main config
        r = self.run_cmd(f"cat {self.MAIN_CONF} 2>/dev/null")
        if r["success"]:
            configs.append(f"# === {self.MAIN_CONF} ===\n{r['stdout']}")
        
        # Drop-in configs
        if os.path.isdir(self.CONF_DIR):
            for f in sorted(os.listdir(self.CONF_DIR)):
                if f.endswith(".conf"):
                    r = self.run_cmd(f"cat {self.CONF_DIR}/{f} 2>/dev/null")
                    if r["success"]:
                        configs.append(f"# === {f} ===\n{r['stdout']}")
        
        return "\n\n".join(configs)
