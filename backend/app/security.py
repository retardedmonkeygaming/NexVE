from itsdangerous import URLSafeTimedSerializer
import secrets
import os

SECRET_KEY = os.environ.get("NEXVE_SECRET", secrets.token_hex(32))
csrf_serializer = URLSafeTimedSerializer(SECRET_KEY)

def generate_csrf_token(session_token: str) -> str:
    return csrf_serializer.dumps(session_token, salt="csrf")

def validate_csrf_token(token: str, session_token: str, max_age: int = 3600) -> bool:
    try:
        result = csrf_serializer.loads(token, salt="csrf", max_age=max_age)
        return result == session_token
    except Exception:
        return False
