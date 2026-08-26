"""
NexVE Notification Service
Manages notification delivery via email, webhook, Slack, Discord, etc.
"""
import subprocess
import json
import urllib.request
import urllib.error
from typing import List, Optional


class NotificationService:
    """Manages notification delivery."""

    def send_email(self, to: str, subject: str, body: str,
                  smtp_host: str = "localhost", smtp_port: int = 25,
                  username: str = "", password: str = "") -> dict:
        """Send email notification."""
        try:
            # Use system sendmail or python smtplib
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg["Subject"] = f"[NexVE] {subject}"
            msg["From"] = f"nexve@{subprocess.run('hostname', shell=True, capture_output=True, text=True).stdout.strip()}"
            msg["To"] = to

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if username and password:
                    server.starttls()
                    server.login(username, password)
                server.send_message(msg)

            return {"success": True, "method": "email", "to": to}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_webhook(self, url: str, payload: dict, 
                    headers: dict = None) -> dict:
        """Send webhook notification."""
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "NexVE/3.0",
                    **(headers or {}),
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return {
                    "success": True,
                    "method": "webhook",
                    "status": resp.status,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_slack(self, webhook_url: str, message: str, 
                  channel: str = "", level: str = "info") -> dict:
        """Send Slack notification."""
        try:
            colors = {
                "info": "#3b82f6",
                "warning": "#f59e0b",
                "error": "#ef4444",
                "critical": "#ef4444",
                "success": "#22c55e",
            }

            payload = {
                "attachments": [{
                    "color": colors.get(level, "#606070"),
                    "title": "NexVE Notification",
                    "text": message,
                    "footer": "NexVE v3.0",
                }]
            }
            if channel:
                payload["channel"] = channel

            return self.send_webhook(webhook_url, payload)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_discord(self, webhook_url: str, message: str,
                    level: str = "info") -> dict:
        """Send Discord notification."""
        try:
            colors = {
                "info": 0x3b82f6,
                "warning": 0xf59e0b,
                "error": 0xef4444,
                "critical": 0xef4444,
                "success": 0x22c55e,
            }

            payload = {
                "embeds": [{
                    "title": "NexVE Notification",
                    "description": message,
                    "color": colors.get(level, 0x606070),
                }]
            }

            return self.send_webhook(webhook_url, payload)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_telegram(self, bot_token: str, chat_id: str, message: str) -> dict:
        """Send Telegram notification."""
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": f"🖥️ *NexVE*\n\n{message}",
                "parse_mode": "Markdown",
            }
            return self.send_webhook(url, payload)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_notification(self, target_type: str, config: dict,
                         message: str, level: str = "info") -> dict:
        """Send notification via the specified target type."""
        if target_type == "email":
            return self.send_email(
                to=config.get("to", ""),
                subject=config.get("subject", "NexVE Alert"),
                body=message,
                smtp_host=config.get("smtp_host", "localhost"),
                smtp_port=config.get("smtp_port", 25),
                username=config.get("username", ""),
                password=config.get("password", ""),
            )
        elif target_type == "webhook":
            return self.send_webhook(
                url=config.get("url", ""),
                payload={"message": message, "level": level},
                headers=config.get("headers", {}),
            )
        elif target_type == "slack":
            return self.send_slack(
                webhook_url=config.get("webhook_url", ""),
                message=message,
                level=level,
            )
        elif target_type == "discord":
            return self.send_discord(
                webhook_url=config.get("webhook_url", ""),
                message=message,
                level=level,
            )
        elif target_type == "telegram":
            return self.send_telegram(
                bot_token=config.get("bot_token", ""),
                chat_id=config.get("chat_id", ""),
                message=message,
            )
        else:
            return {"success": False, "error": f"Unknown notification type: {target_type}"}

    def test_notification(self, target_type: str, config: dict) -> dict:
        """Send a test notification."""
        return self.send_notification(
            target_type, config,
            message="This is a test notification from NexVE v3.0.\n"
                   f"If you received this, {target_type} notifications are working!",
            level="info",
        )
