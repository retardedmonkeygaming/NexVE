"""
NexVE Console Service
Manages VM console access via noVNC, SPICE, serial, and xterm.js.
"""
import subprocess
import os
import json
import signal
from typing import Optional, Dict


class ConsoleService:
    """Manages VM console access."""

    def __init__(self):
        self.websockify_procs = {}

    def get_vnc_info(self, vm_name: str) -> dict:
        """Get VNC connection info for a VM."""
        try:
            r = subprocess.run(
                f"virsh vncdisplay {vm_name} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0 and r.stdout.strip():
                display = r.stdout.strip()
                # Parse display number (e.g., :0 -> port 5900)
                display_num = int(display.lstrip(":")) if display.lstrip(":").isdigit() else 0
                port = 5900 + display_num

                return {
                    "available": True,
                    "display": display,
                    "port": port,
                    "host": "0.0.0.0",
                    "websocket_port": port + 10000,  # websockify port
                }
            return {"available": False, "error": "VNC not enabled for this VM"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def start_websockify(self, vm_name: str, vnc_port: int = 5900,
                        ws_port: int = 6080) -> dict:
        """Start websockify proxy for VNC."""
        try:
            # Check if websockify is available
            check = subprocess.run(
                "which websockify 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True
            )
            if not check.stdout.strip():
                return {"success": False, "error": "websockify not installed"}

            # Kill existing process for this VM
            if vm_name in self.websockify_procs:
                try:
                    os.kill(self.websockify_procs[vm_name], signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass

            # Start websockify in background
            proc = subprocess.Popen(
                f"websockify --web /usr/share/novnc {ws_port} 127.0.0.1:{vnc_port}",
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.websockify_procs[vm_name] = proc.pid

            return {
                "success": True,
                "pid": proc.pid,
                "ws_port": ws_port,
                "url": f"/websockify/?host=127.0.0.1&port={ws_port}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_websockify(self, vm_name: str) -> dict:
        """Stop websockify proxy for a VM."""
        try:
            if vm_name in self.websockify_procs:
                pid = self.websockify_procs[vm_name]
                os.kill(pid, signal.SIGTERM)
                del self.websockify_procs[vm_name]
            return {"success": True}
        except Exception:
            return {"success": True}

    def get_spice_info(self, vm_name: str) -> dict:
        """Get SPICE connection info for a VM."""
        try:
            r = subprocess.run(
                f"virsh domdisplay {vm_name} 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if r.returncode == 0:
                output = r.stdout.strip()
                if "spice" in output.lower():
                    return {
                        "available": True,
                        "uri": output,
                        "port": 5900,  # Default SPICE port
                    }
            return {"available": False, "error": "SPICE not enabled for this VM"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_serial_info(self, vm_name: str) -> dict:
        """Get serial console info for a VM."""
        try:
            # Check if serial console is configured
            r = subprocess.run(
                f"virsh dominfo {vm_name} 2>/dev/null | grep -i serial",
                shell=True, capture_output=True, text=True, timeout=5
            )
            has_serial = "pty" in r.stdout.lower() or "serial" in r.stdout.lower()

            if has_serial:
                return {
                    "available": True,
                    "type": "pty",
                    "command": f"virsh console {vm_name}",
                }
            return {"available": False, "error": "Serial console not configured"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_container_console(self, ct_id: int) -> dict:
        """Get container console info."""
        try:
            # Check if pct is available
            check = subprocess.run(
                "which pct 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True
            )
            if check.stdout.strip():
                return {
                    "available": True,
                    "type": "lxc",
                    "command": f"pct enter {ct_id}",
                    "exec_command": f"pct exec {ct_id} -- /bin/bash",
                }

            # Fallback: check if lxc-attach is available
            check2 = subprocess.run(
                "which lxc-attach 2>/dev/null || echo ''",
                shell=True, capture_output=True, text=True
            )
            if check2.stdout.strip():
                return {
                    "available": True,
                    "type": "lxc",
                    "command": f"lxc-attach -n {ct_id}",
                }

            return {"available": False, "error": "No container runtime found"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_console_types(self, vm_name: str) -> list:
        """Get available console types for a VM."""
        types = []

        vnc = self.get_vnc_info(vm_name)
        if vnc.get("available"):
            types.append({"type": "vnc", "label": "noVNC", "available": True})

        spice = self.get_spice_info(vm_name)
        if spice.get("available"):
            types.append({"type": "spice", "label": "SPICE", "available": True})

        serial = self.get_serial_info(vm_name)
        if serial.get("available"):
            types.append({"type": "serial", "label": "Serial Console", "available": True})

        # xterm.js is always available via WebSocket
        types.append({"type": "xterm", "label": "xterm.js", "available": True})

        return types
