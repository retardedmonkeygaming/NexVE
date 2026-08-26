"""Shell: WebSocket-based terminal and command execution."""
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from ..auth import get_current_user
import subprocess
import os
import pty
import select
import struct
import fcntl
import termios
import signal

router = APIRouter()


def auth_check(request: Request):
    user = get_current_user(request)
    if not user:
        return None, RedirectResponse(url="/login", status_code=302)
    return user, None


# ─── WebSocket Shell ───

@router.websocket("/ws")
async def shell_websocket(websocket: WebSocket):
    """WebSocket terminal — spawns a real bash shell."""
    await websocket.accept()

    # Simple token check from query param
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001)
        return

    from ..database import SessionLocal
    from ..models.user import Session, User
    from datetime import datetime
    db = SessionLocal()
    try:
        session = db.query(Session).filter(
            Session.token == token,
            Session.expires_at > datetime.utcnow()
        ).first()
        if not session:
            await websocket.close(code=4001)
            return
        user = db.query(User).filter(User.id == session.user_id).first()
        if not user:
            await websocket.close(code=4001)
            return
    finally:
        db.close()

    # Spawn a real PTY with bash
    child_pid, fd = pty.openpty()
    if child_pid == 0:
        # Child process
        os.environ["TERM"] = "xterm-256color"
        os.environ["HOME"] = "/root"
        os.execvp("/bin/bash", ["/bin/bash", "--login"])
    else:
        # Parent process
        # Set non-blocking
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        try:
            while True:
                # Read from PTY and send to WebSocket
                try:
                    data = os.read(fd, 4096)
                    if data:
                        await websocket.send_text(data.decode("utf-8", errors="replace"))
                except (OSError, IOError):
                    pass

                # Read from WebSocket and write to PTY
                try:
                    data = await websocket.receive_text()
                    if data:
                        os.write(fd, data.encode("utf-8"))
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

                import time
                time.sleep(0.01)
        finally:
            try:
                os.close(fd)
                os.kill(child_pid, signal.SIGTERM)
                os.waitpid(child_pid, 0)
            except Exception:
                pass


# ─── Fallback: HTTP command execution ───

@router.post("/exec")
async def shell_exec(request: Request, command: str = "", cwd: str = "/"):
    """Execute a shell command and return the output (fallback if WebSocket unavailable)."""
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
