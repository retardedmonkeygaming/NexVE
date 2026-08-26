from itsdangerous import URLSafeTimedSerializer
import secrets
import os

SECRET_KEY_FILE = "/opt/nexve/data/.secret_key"

def _load_or_create_secret() -> str:
    """Load secret key from env, file, or generate and persist a new one."""
    # 1. Environment variable (highest priority)
    env_key = os.environ.get("NEXVE_SECRET")
    if env_key:
        return env_key

    # 2. Existing file
    try:
        with open(SECRET_KEY_FILE, "r") as f:
            key = f.read().strip()
            if len(key) >= 16:
                return key
    except (FileNotFoundError, PermissionError):
        pass

    # 3. Generate new key and persist it
    key = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(SECRET_KEY_FILE), exist_ok=True)
        with open(SECRET_KEY_FILE, "w") as f:
            f.write(key)
        os.chmod(SECRET_KEY_FILE, 0o600)
    except (PermissionError, OSError):
        pass  # In-memory only as last resort
    return key


SECRET_KEY = _load_or_create_secret()
csrf_serializer = URLSafeTimedSerializer(SECRET_KEY)


def generate_csrf_token(session_token: str) -> str:
    return csrf_serializer.dumps(session_token, salt="csrf")


def validate_csrf_token(token: str, session_token: str, max_age: int = 3600) -> bool:
    try:
        result = csrf_serializer.loads(token, salt="csrf", max_age=max_age)
        return result == session_token
    except Exception:
        return False
