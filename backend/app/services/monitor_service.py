"""
NexVE Monitor Service v3.0
Reliable metrics collection with fallback for missing directories.
"""
import subprocess
import json
import psutil
from datetime import datetime, timedelta
from ..database import SessionLocal
from ..models.vm import VM
import threading
import time
import os

HISTORY_FILE = os.path.expanduser("~/.nexve/metrics.jsonl")
MAX_HISTORY_HOURS = 24


class MonitorService:
    def __init__(self):
        self._running = False
        self._last_snapshot = None

    def start_collector(self):
        """Start background metrics collection every 5 seconds."""
        if self._running:
            return
        self._running = True

        def collect():
            # First snapshot initializes cpu_percent properly
            psutil.cpu_percent(interval=None)
            time.sleep(1)
            while self._running:
                try:
                    metric = self._snapshot()
                    self._last_snapshot = metric
                    self._append_metric(metric)
                except Exception:
                    pass
                time.sleep(5)

        t = threading.Thread(target=collect, daemon=True)
        t.start()

    def stop_collector(self):
        self._running = False

    def _snapshot(self) -> dict:
        try:
            cpu = psutil.cpu_percent(interval=0.1)
        except Exception:
            cpu = 0.0
        try:
            cpu_count = psutil.cpu_count(logical=True) or 1
        except Exception:
            cpu_count = 1
        try:
            cpu_freq = psutil.cpu_freq()
        except Exception:
            cpu_freq = None
        try:
            mem = psutil.virtual_memory()
        except Exception:
            mem = None
        try:
            disk = psutil.disk_usage("/")
        except Exception:
            disk = None
        try:
            net = psutil.net_io_counters()
        except Exception:
            net = None
        try:
            load = os.getloadavg()
        except Exception:
            load = (0.0, 0.0, 0.0)
        try:
            boot = psutil.boot_time()
            uptime = int(time.time() - boot)
        except Exception:
            uptime = 0

        # Calculate network rates
        net_sent_rate = 0
        net_recv_rate = 0
        if net:
            prev_sent = getattr(self, '_prev_net_sent', 0)
            prev_recv = getattr(self, '_prev_net_recv', 0)
            prev_time = getattr(self, '_prev_net_time', 0)
            now = time.time()
            dt = now - prev_time if prev_time > 0 else 1.0
            if dt > 0:
                net_sent_rate = int((net.bytes_sent - prev_sent) / dt)
                net_recv_rate = int((net.bytes_recv - prev_recv) / dt)
            self._prev_net_sent = net.bytes_sent
            self._prev_net_recv = net.bytes_recv
            self._prev_net_time = now

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": round(cpu, 1),
            "cpu_count": cpu_count,
            "cpu_freq_current": round(cpu_freq.current, 0) if cpu_freq else 0,
            "cpu_freq_max": round(cpu_freq.max, 0) if cpu_freq and cpu_freq.max else 0,
            "memory_percent": round(mem.percent, 1) if mem else 0,
            "memory_used_mb": (mem.used // (1024 * 1024)) if mem else 0,
            "memory_total_mb": (mem.total // (1024 * 1024)) if mem else 0,
            "memory_available_mb": (mem.available // (1024 * 1024)) if mem else 0,
            "disk_percent": round(disk.percent, 1) if disk else 0,
            "disk_used_gb": round(disk.used / (1024 ** 3), 1) if disk else 0,
            "disk_total_gb": round(disk.total / (1024 ** 3), 1) if disk else 0,
            "disk_free_gb": round(disk.free / (1024 ** 3), 1) if disk else 0,
            "net_sent_bytes": net.bytes_sent if net else 0,
            "net_recv_bytes": net.bytes_recv if net else 0,
            "net_sent_rate": net_sent_rate,
            "net_recv_rate": net_recv_rate,
            "load_1": round(load[0], 2),
            "load_5": round(load[1], 2),
            "load_15": round(load[2], 2),
            "uptime": uptime,
        }

    def _append_metric(self, metric: dict):
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, "a") as f:
                f.write(json.dumps(metric) + "\n")
            # Prune old entries periodically
            cutoff = (datetime.utcnow() - timedelta(hours=MAX_HISTORY_HOURS)).isoformat()
            self._prune(cutoff)
        except Exception:
            pass

    def _prune(self, cutoff: str):
        if not os.path.exists(HISTORY_FILE):
            return
        try:
            lines = []
            with open(HISTORY_FILE, "r") as f:
                for line in f:
                    try:
                        m = json.loads(line)
                        if m.get("timestamp", "") > cutoff:
                            lines.append(line)
                    except (json.JSONDecodeError, KeyError):
                        pass
            with open(HISTORY_FILE, "w") as f:
                f.writelines(lines)
        except Exception:
            pass

    def get_history(self, hours: int = 24) -> list:
        if not os.path.exists(HISTORY_FILE):
            return []
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        metrics = []
        try:
            with open(HISTORY_FILE, "r") as f:
                for line in f:
                    try:
                        m = json.loads(line)
                        if m.get("timestamp", "") > cutoff:
                            metrics.append(m)
                    except (json.JSONDecodeError, KeyError):
                        pass
        except Exception:
            pass
        return metrics

    def get_current(self) -> dict:
        if self._last_snapshot:
            return self._last_snapshot
        return self._snapshot()

    def get_vm_metrics(self, vm_name: str) -> dict:
        """Get live resource usage for a VM via virsh."""
        try:
            r = subprocess.run(
                f"virsh domstats {vm_name}",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return {"error": "VM not running or virsh not available"}
            stats = {}
            for line in r.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    try:
                        stats[k.strip()] = int(v.strip())
                    except ValueError:
                        stats[k.strip()] = v.strip()
            return stats
        except Exception:
            return {}
