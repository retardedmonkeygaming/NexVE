import subprocess
import os
import signal
import json
from typing import Optional


class ConsoleService:
    """Manages VNC/noVNC console sessions for VMs and containers."""

    # noVNC path on Debian
    NOVNC_PATH = "/usr/share/novnc"
    WEBSOCKIFY = "/usr/bin/websockify"

    def __init__(self):
        self.processes = {}  # port -> subprocess

    def start_novnc(self, vm_id: int, vnc_port: int) -> dict:
        """Start a websockify proxy for noVNC. Returns the websocket URL."""
        ws_port = 6080 + vm_id  # unique WS port per VM
        # Kill existing if running
        if ws_port in self.processes:
            self.stop_novnc(vm_id)

        try:
            proc = subprocess.Popen(
                [
                    self.WEBSOCKIFY,
                    "--web", self.NOVNC_PATH,
                    str(ws_port),
                    f"localhost:{vnc_port}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.processes[ws_port] = proc
            return {
                "success": True,
                "ws_port": ws_port,
                "url": f"ws://0.0.0.0:{ws_port}/websockify",
                "novnc_url": f"/static/novnc/vnc.html?autoconnect=true&resize=scale&path=ws://0.0.0.0:{ws_port}/websockify",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop_novnc(self, vm_id: int) -> dict:
        ws_port = 6080 + vm_id
        if ws_port in self.processes:
            try:
                self.processes[ws_port].terminate()
                self.processes[ws_port].wait(timeout=5)
            except Exception:
                try:
                    self.processes[ws_port].kill()
                except Exception:
                    pass
            del self.processes[ws_port]
        return {"success": True}

    def get_vnc_port(self, vm_id: int) -> int:
        """Get VNC display port for a VM via libvirt."""
        try:
            import libvirt
            conn = libvirt.open("qemu:///system")
            if conn:
                dom = conn.lookupByID(vm_id)
                if dom:
                    xml = dom.XMLDesc(0)
                    # Parse VNC port from XML
                    import re
                    match = re.search(r'port=\'(\d+)\'', xml)
                    if match:
                        return int(match.group(1))
                    # Try graphics info
                    if dom.isActive():
                        info = dom.graphicsStats(0)
                        return info.get("port", 5900 + vm_id)
                conn.close()
        except Exception:
            pass
        return 5900 + vm_id  # default VNC port

    def console_for_vm(self, vm_id: int) -> dict:
        """Start noVNC session and return connection info."""
        vnc_port = self.get_vnc_port(vm_id)
        return self.start_novnc(vm_id, vnc_port)

    def console_for_container(self, ct_id: int) -> dict:
        """For LXC containers, use attach with a terminal instead.
        Returns info for a simple web terminal via xterm.js."""
        # Containers don't use VNC — they use attach. We return info
        # for the frontend to open a WebSocket shell session.
        return {
            "success": True,
            "type": "shell",
            "url": f"/api/console/shell/{ct_id}",
        }


console_svc = ConsoleService()
