from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from ..auth import get_current_user
import subprocess

router = APIRouter()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


@router.post("/api/shell/exec")
async def shell_exec(request: Request, command: str = "", cwd: str = "/"):
    """Execute a shell command and return the output."""
    user, redir = auth_check(request)
    if redir:
        return redir
    try:
        r = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
        return JSONResponse({
            "success": r.returncode == 0,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "returncode": r.returncode,
        })
    except subprocess.TimeoutExpired:
        return JSONResponse({
            "success": False,
            "stdout": "",
            "stderr": "Command timed out after 30 seconds",
            "returncode": -1,
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
        })
