"""
NexVE OpenID Connect Service
Provides OpenID Connect (OIDC) authentication integration.
"""
import hashlib
import secrets
import json
import time
from typing import Optional


class OIDCService:
    """Manages OpenID Connect authentication."""

    def __init__(self):
        self._state_store = {}  # state -> {redirect_uri, created_at}

    def is_configured(self) -> bool:
        """Check if OIDC is configured."""
        try:
            from ..database import SessionLocal
            from ..models.enhanced_models import SystemSetting
            db = SessionLocal()
            try:
                setting = db.query(SystemSetting).filter(SystemSetting.key == "oidc_enabled").first()
                return setting and setting.value == "true"
            finally:
                db.close()
        except Exception:
            return False

    def get_config(self) -> dict:
        """Get OIDC configuration."""
        try:
            from ..database import SessionLocal
            from ..models.enhanced_models import SystemSetting
            db = SessionLocal()
            try:
                keys = ["oidc_enabled", "oidc_issuer", "oidc_client_id", "oidc_redirect_uri", "oidc_scope"]
                config = {}
                for key in keys:
                    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
                    config[key.replace("oidc_", "")] = setting.value if setting else ""
                config["client_secret"] = "***" if config.get("client_id") else ""
                return config
            finally:
                db.close()
        except Exception:
            return {}

    def save_config(self, issuer: str, client_id: str, client_secret: str,
                    redirect_uri: str = "", scope: str = "openid email profile") -> dict:
        """Save OIDC configuration."""
        try:
            from ..database import SessionLocal
            from ..models.enhanced_models import SystemSetting
            db = SessionLocal()
            try:
                config = {
                    "oidc_enabled": "true",
                    "oidc_issuer": issuer,
                    "oidc_client_id": client_id,
                    "oidc_client_secret": client_secret,
                    "oidc_redirect_uri": redirect_uri or f"{self._get_base_url()}/auth/oidc/callback",
                    "oidc_scope": scope,
                }
                for key, value in config.items():
                    existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
                    if existing:
                        existing.value = value
                    else:
                        db.add(SystemSetting(key=key, value=value))
                db.commit()
                return {"success": True}
            finally:
                db.close()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_auth_url(self) -> dict:
        """Generate OIDC authorization URL."""
        config = self.get_config()
        if not config.get("client_id") or not config.get("issuer"):
            return {"success": False, "error": "OIDC not configured"}

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        self._state_store[state] = {"created_at": time.time()}

        issuer = config["issuer"].rstrip("/")
        client_id = config["client_id"]
        redirect_uri = config["redirect_uri"]
        scope = config.get("scope", "openid email profile")

        auth_url = (
            f"{issuer}/authorize?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={scope}&"
            f"state={state}&"
            f"nonce={nonce}"
        )

        return {"success": True, "auth_url": auth_url, "state": state}

    def validate_state(self, state: str) -> bool:
        """Validate the OIDC state parameter."""
        if state not in self._state_store:
            return False
        entry = self._state_store.pop(state)
        # State expires after 10 minutes
        return (time.time() - entry["created_at"]) < 600

    def disable(self) -> dict:
        """Disable OIDC authentication."""
        try:
            from ..database import SessionLocal
            from ..models.enhanced_models import SystemSetting
            db = SessionLocal()
            try:
                setting = db.query(SystemSetting).filter(SystemSetting.key == "oidc_enabled").first()
                if setting:
                    setting.value = "false"
                db.commit()
                return {"success": True}
            finally:
                db.close()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_base_url(self) -> str:
        """Get the base URL of the application."""
        return "http://localhost:8000"
