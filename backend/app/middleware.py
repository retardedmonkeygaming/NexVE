from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from .database import SessionLocal
from .models.user import User


class SetupMiddleware(BaseHTTPMiddleware):
    ALLOWED_PATHS = {"/setup", "/api/setup", "/static"}

    async def dispatch(self, request, call_next):
        path = request.url.path

        if any(path.startswith(p) for p in self.ALLOWED_PATHS):
            return await call_next(request)

        db = SessionLocal()
        try:
            user_count = db.query(User).count()
        finally:
            db.close()

        if user_count == 0:
            return RedirectResponse(url="/setup", status_code=302)

        return await call_next(request)
