"""Shell: WebSocket-based terminal and command execution."""
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from ..auth import get_current_user, api_auth
import subprocess
import os
import pty
import select
import signal
import struct
import fcntl
import termios
import asyncio

router = APIRouter()



# ─── WebSocket Shell ───

@router.websocket("/ws")
async def shell_websocket(websocket: WebSocket):
    """WebSocket terminal — spawns a real bash shell via fork+pty."""
    await websocket.accept()

    # Token check from query param
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

    # Create PTY pair
    master_fd, slave_fd = pty.openpty()

    # Fork to create child process
    child_pid = os.fork()

    if child_pid == 0:
        # ── Child process ──
        os.close(master_fd)
        os.setsid()

        # Make slave the controlling terminal
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

        # Redirect stdio to slave
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)

        # Set terminal environment
        os.environ["TERM"] = "xterm-256color"
        os.environ["HOME"] = "/root"
        os.environ["SHELL"] = "/bin/bash"

        os.execvp("/bin/bash", ["/bin/bash", "--login"])
    else:
        # ── Parent process ──
        os.close(slave_fd)

        # Set master_fd non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        loop = asyncio.get_event_loop()
        child_alive = True

        async def read_pty():
            """Read from PTY and send to WebSocket."""
            nonlocal child_alive
            while child_alive:
                try:
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if ready:
                        data = os.read(master_fd, 4096)
                        if data:
                            await websocket.send_text(
                                data.decode("utf-8", errors="replace")
                            )
                        else:
                            # EOF — child exited
                            child_alive = False
                            break
                except (OSError, IOError):
                    await asyncio.sleep(0.05)
                except Exception:
                    child_alive = False
                    break
                await asyncio.sleep(0)  # yield to event loop

        async def read_ws():
            """Read from WebSocket and write to PTY."""
            nonlocal child_alive
            while child_alive:
                try:
                    data = await websocket.receive_text()
                    if data:
                        os.write(master_fd, data.encode("utf-8"))
                except WebSocketDisconnect:
                    child_alive = False
                    break
                except Exception:
                    child_alive = False
                    break

        try:
            # Run both readers concurrently
            await asyncio.gather(read_pty(), read_ws())
        finally:
            try:
                os.close(master_fd)
            except Exception:
                pass
            try:
                os.kill(child_pid, signal.SIGTERM)
                os.waitpid(child_pid, os.WNOHANG)
            except Exception:
                pass


# ─── Fallback: HTTP command execution ───

@router.post("/exec")
async def shell_exec(request: Request, command: str = "", cwd: str = "/"):
    """Execute a shell command and return the output (fallback if WebSocket unavailable)."""
    user, error = api_auth(request)
    if error: return error
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
