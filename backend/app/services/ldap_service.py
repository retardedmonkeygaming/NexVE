"""LDAP / Active Directory authentication integration."""
import ssl
import hashlib
from typing import Optional, List


class LDAPService:
    """LDAP integration for user authentication and group-based role mapping."""

    def __init__(self):
        self._conn = None

    def _get_config(self):
        """Load LDAP config from database."""
        try:
            from ..database import SessionLocal
            from ..models.feature_models import LDAPConfig
            db = SessionLocal()
            try:
                config = db.query(LDAPConfig).first()
                return config
            finally:
                db.close()
        except Exception:
            return None

    def test_connection(self, host: str = "", port: int = 636, use_tls: bool = True, bind_dn: str = "", bind_password: str = "") -> dict:
        """Test LDAP connection."""
        config = self._get_config()
        if not config and not host:
            return {"success": False, "error": "No LDAP configuration found"}

        host = host or config.host
        port = port or config.port
        use_tls = use_tls if host else config.use_tls
        bind_dn = bind_dn or config.bind_dn
        bind_password = bind_password or config.bind_password

        try:
            import ldap3
            server = ldap3.Server(
                host, port=port, use_ssl=use_tls,
                get_info=ldap3.ALL,
            )
            conn = ldap3.Connection(
                server, user=bind_dn, password=bind_password,
                auto_bind=True,
            )
            result = {
                "success": True,
                "server_info": str(server.info),
                "entries": conn.entries.__len__() if hasattr(conn, "entries") else 0,
            }
            conn.unbind()
            return result
        except ImportError:
            return {"success": False, "error": "ldap3 package not installed. Install with: pip install ldap3"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def authenticate(self, username: str, password: str) -> dict:
        """Authenticate a user against LDAP and return role mapping."""
        config = self._get_config()
        if not config or not config.enabled:
            return {"success": False, "error": "LDAP not configured or disabled"}

        try:
            import ldap3

            server = ldap3.Server(
                config.host, port=config.port,
                use_ssl=config.use_tls, get_info=ldap3.ALL,
            )

            # First bind with service account
            conn = ldap3.Connection(
                server, user=config.bind_dn, password=config.bind_password,
                auto_bind=True,
            )

            # Search for the user
            search_filter = f"({config.username_attr}={username})"
            conn.search(config.base_dn, search_filter, attributes=[config.username_attr, config.email_attr, "memberOf"])

            if not conn.entries:
                conn.unbind()
                return {"success": False, "error": "User not found in LDAP"}

            ldap_entry = conn.entries[0]
            user_dn = ldap_entry.entry_dn

            # Try to bind as the user to verify password
            user_conn = ldap3.Connection(
                server, user=user_dn, password=password,
                auto_bind=True,
            )

            # Determine role from group membership
            role = "user"
            groups = []
            if hasattr(ldap_entry, "memberOf"):
                member_of = ldap_entry.memberOf
                if member_of:
                    for g in (member_of if isinstance(member_of, list) else [member_of]):
                        group_name = str(g).split(",")[0].split("=")[1] if "=" in str(g) else str(g)
                        groups.append(group_name)

            if config.admin_group in groups:
                role = "admin"
            elif config.auditor_group in groups:
                role = "auditor"

            email = str(ldap_entry.get(config.email_attr, "")) if hasattr(ldap_entry, config.email_attr) else ""

            user_conn.unbind()
            conn.unbind()

            return {
                "success": True,
                "username": str(ldap_entry.get(config.username_attr, username)),
                "email": email,
                "role": role,
                "groups": groups,
            }
        except ImportError:
            return {"success": False, "error": "ldap3 package not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_users(self, query: str = "") -> List[dict]:
        """Search LDAP for users."""
        config = self._get_config()
        if not config or not config.enabled:
            return []

        try:
            import ldap3

            server = ldap3.Server(
                config.host, port=config.port,
                use_ssl=config.use_tls, get_info=ldap3.ALL,
            )
            conn = ldap3.Connection(
                server, user=config.bind_dn, password=config.bind_password,
                auto_bind=True,
            )

            search_filter = config.user_filter
            if query:
                search_filter = f"(&{config.user_filter}({config.username_attr}=*{query}*))"

            conn.search(config.base_dn, search_filter, attributes=[config.username_attr, config.email_attr, "memberOf"])

            users = []
            for entry in conn.entries:
                users.append({
                    "username": str(entry.get(config.username_attr, "")),
                    "email": str(entry.get(config.email_attr, "")),
                })

            conn.unbind()
            return users
        except Exception:
            return []

