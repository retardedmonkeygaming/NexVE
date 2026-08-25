import subprocess
import json
import psutil
from datetime import datetime, timedelta
from ..database import SessionLocal
from ..models.vm import VM
import threading
import time
import os

HISTORY_FILE = "/opt/nexve/data/metrics.jsonl"
MAX_HISTORY_HOURS = 24


class MonitorService:
    def __init__(self):
        self._running = False

    def start_collector(self):
        """Start background metrics collection every 30 seconds."""
        if self._running:
            return
        self._running = True

        def collect():
            while self._running:
                try:
                    metric = self._snapshot()
                    self._append_metric(metric)
                except Exception:
                    pass
                time.sleep(30)

        t = threading.Thread(target=collect, daemon=True)
        t.start()

    def stop_collector(self):
        self._running = False

    def _snapshot(self) -> dict:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        load = os.getloadavg()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_mb": mem.used // (1024 * 1024),
            "memory_total_mb": mem.total // (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024 ** 3), 1),
            "disk_total_gb": round(disk.total / (1024 ** 3), 1),
            "net_sent_bytes": net.bytes_sent,
            "net_recv_bytes": net.bytes_recv,
            "load_1": round(load[0], 2),
            "load_5": round(load[1], 2),
            "load_15": round(load[2], 2),
        }

    def _append_metric(self, metric: dict):
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(metric) + "\n")

        # Prune old entries
        cutoff = (datetime.utcnow() - timedelta(hours=MAX_HISTORY_HOURS)).isoformat()
        self._prune(cutoff)

    def _prune(self, cutoff: str):
        if not os.path.exists(HISTORY_FILE):
            return
        lines = []
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                try:
                    m = json.loads(line)
                    if m["timestamp"] > cutoff:
                        lines.append(line)
                except (json.JSONDecodeError, KeyError):
                    pass
        with open(HISTORY_FILE, "w") as f:
            f.writelines(lines)

    def get_history(self, hours: int = 1) -> list:
        if not os.path.exists(HISTORY_FILE):
            return []
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        metrics = []
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                try:
                    m = json.loads(line)
                    if m["timestamp"] > cutoff:
                        metrics.append(m)
                except (json.JSONDecodeError, KeyError):
                    pass
        return metrics

    def get_current(self) -> dict:
        return self._snapshot()

    def get_vm_metrics(self, vm_name: str) -> dict:
        """Get live resource usage for a VM via virsh."""
        try:
            r = subprocess.run(
                f"virsh domstats {vm_name}",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                return {}
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
