"""
NexVE ACME Service
Manages SSL/TLS certificates via Let's Encrypt and other ACME providers.
"""
import subprocess
import os
import json
from datetime import datetime
from typing import List


class ACMEService:
    """Manages ACME/Let's Encrypt certificates."""

    def __init__(self):
        self.cert_dir = "/etc/nexve/ssl"
        os.makedirs(self.cert_dir, exist_ok=True)

    def get_status(self) -> dict:
        """Get ACME status."""
        try:
            # Check if certbot or acme.sh is available
            certbot = subprocess.run(
                "which certbot 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True
            )
            acme_sh = subprocess.run(
                "which acme.sh 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True
            )

            return {
                "certbot_available": bool(certbot.stdout.strip()),
                "acme_sh_available": bool(acme_sh.stdout.strip()),
                "cert_dir": self.cert_dir,
            }
        except Exception:
            return {"certbot_available": False, "acme_sh_available": False}

    def list_certificates(self) -> List[dict]:
        """List managed certificates."""
        try:
            certs = []
            if os.path.exists(self.cert_dir):
                for f in os.listdir(self.cert_dir):
                    if f.endswith(".pem") or f.endswith(".crt"):
                        cert_path = os.path.join(self.cert_dir, f)
                        # Get cert info
                        info = self._get_cert_info(cert_path)
                        certs.append({
                            "name": f,
                            "path": cert_path,
                            "domain": info.get("subject", ""),
                            "issuer": info.get("issuer", ""),
                            "expires": info.get("not_after", ""),
                        })
            return certs
        except Exception:
            return []

    def _get_cert_info(self, cert_path: str) -> dict:
        """Get certificate information via openssl."""
        try:
            r = subprocess.run(
                f"openssl x509 -in {cert_path} -noout -subject -issuer -dates 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            info = {}
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if "subject=" in line:
                        info["subject"] = line.split("=", 1)[1].strip()
                    elif "issuer=" in line:
                        info["issuer"] = line.split("=", 1)[1].strip()
                    elif "notAfter=" in line:
                        info["not_after"] = line.split("=", 1)[1].strip()
            return info
        except Exception:
            return {}

    def provision_certificate(self, domain: str, email: str = "",
                             challenge_type: str = "http") -> dict:
        """Provision a new certificate using certbot."""
        try:
            cmd = f"certbot certonly --non-interactive --agree-tos"

            if email:
                cmd += f" --email {email}"
            else:
                cmd += " --register-unsafely-without-email"

            if challenge_type == "http":
                cmd += " --standalone"
            elif challenge_type == "dns":
                cmd += " --dns-cloudflare"  # Default DNS provider

            cmd += f" -d {domain}"

            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120
            )

            if r.returncode == 0:
                # Copy certs to our directory
                live_dir = f"/etc/letsencrypt/live/{domain}"
                if os.path.exists(live_dir):
                    import shutil
                    dest_cert = os.path.join(self.cert_dir, f"{domain}.crt")
                    dest_key = os.path.join(self.cert_dir, f"{domain}.key")
                    shutil.copy2(f"{live_dir}/fullchain.pem", dest_cert)
                    shutil.copy2(f"{live_dir}/privkey.pem", dest_key)
                    return {
                        "success": True,
                        "cert_path": dest_cert,
                        "key_path": dest_key,
                    }

            return {"success": False, "error": r.stderr.strip() or r.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def upload_certificate(self, domain: str, cert_content: str,
                          key_content: str) -> dict:
        """Upload a custom certificate."""
        try:
            cert_path = os.path.join(self.cert_dir, f"{domain}.crt")
            key_path = os.path.join(self.cert_dir, f"{domain}.key")

            with open(cert_path, "w") as f:
                f.write(cert_content)
            with open(key_path, "w") as f:
                f.write(key_content)

            # Set permissions
            os.chmod(key_path, 0o600)

            return {
                "success": True,
                "cert_path": cert_path,
                "key_path": key_path,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_certificate(self, domain: str) -> dict:
        """Apply certificate to NexVE web server (nginx/caddy)."""
        try:
            cert_path = os.path.join(self.cert_dir, f"{domain}.crt")
            key_path = os.path.join(self.cert_dir, f"{domain}.key")

            if not os.path.exists(cert_path) or not os.path.exists(key_path):
                return {"success": False, "error": "Certificate files not found"}

            # Check if nginx is running
            nginx_r = subprocess.run(
                "systemctl is-active nginx 2>/dev/null || echo inactive",
                shell=True, capture_output=True, text=True
            )
            if nginx_r.stdout.strip() == "active":
                # Update nginx config
                nginx_conf = f"""
server {{
    listen 443 ssl http2;
    server_name {domain};
    
    ssl_certificate {cert_path};
    ssl_certificate_key {key_path};
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    location /api/shell/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
"""
                try:
                    with open(f"/etc/nginx/sites-enabled/nexve-ssl.conf", "w") as f:
                        f.write(nginx_conf)
                    subprocess.run(
                        "nginx -t && systemctl reload nginx",
                        shell=True, capture_output=True, timeout=10
                    )
                    return {"success": True, "message": "Certificate applied to nginx"}
                except Exception as e:
                    return {"success": False, "error": f"Nginx config error: {e}"}

            # Check if caddy is running
            caddy_r = subprocess.run(
                "systemctl is-active caddy 2>/dev/null || echo inactive",
                shell=True, capture_output=True, text=True
            )
            if caddy_r.stdout.strip() == "active":
                return {"success": True, "message": "Caddy auto-manages SSL — no action needed"}

            return {"success": True, "message": "Certificate stored. Configure your reverse proxy manually."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def renew_certificates(self) -> dict:
        """Renew all certificates."""
        try:
            r = subprocess.run(
                "certbot renew --non-interactive 2>/dev/null || "
                "acme.sh --renew-all 2>/dev/null || echo 'No ACME client found'",
                shell=True, capture_output=True, text=True, timeout=120
            )
            return {"success": r.returncode == 0, "output": r.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_certificate(self, domain: str) -> dict:
        """Delete a certificate."""
        try:
            cert_path = os.path.join(self.cert_dir, f"{domain}.crt")
            key_path = os.path.join(self.cert_dir, f"{domain}.key")
            if os.path.exists(cert_path):
                os.remove(cert_path)
            if os.path.exists(key_path):
                os.remove(key_path)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
