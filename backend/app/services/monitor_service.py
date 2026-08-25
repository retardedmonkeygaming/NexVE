import psutil
import time
import json
import os
from collections import deque
from typing import Dict


class MonitorService:
    """Collects and stores system metrics in memory (ring buffer) for graphing."""

    MAX_POINTS = 360  # 6 hours at 1-point-per-minute

    def __init__(self):
        self.cpu_history = deque(maxlen=self.MAX_POINTS)
        self.mem_history = deque(maxlen=self.MAX_POINTS)
        self.disk_io_history = deque(maxlen=self.MAX_POINTS)
        self.net_io_history = deque(maxlen=self.MAX_POINTS)
        self.last_disk_io = psutil.disk_io_counters()
        self.last_net_io = psutil.net_io_counters()
        self.last_time = time.time()
        self._collect_initial()

    def _collect_initial(self):
        # Pre-fill with current readings
        now = time.time()
        self.cpu_history.append({"t": now, "v": psutil.cpu_percent(interval=0.1)})
        mem = psutil.virtual_memory()
        self.mem_history.append({"t": now, "v": mem.percent})
        self.disk_io_history.append({"t": now, "v": 0})
        self.net_io_history.append({"t": now, "v": 0})

    def collect(self) -> dict:
        """Call this periodically (e.g. every 10s) to record metrics."""
        now = time.time()
        dt = now - self.last_time if self.last_time else 1

        # CPU
        cpu = psutil.cpu_percent(interval=0)
        self.cpu_history.append({"t": now, "v": cpu})

        # Memory
        mem = psutil.virtual_memory()
        self.mem_history.append({"t": now, "v": mem.percent})

        # Disk I/O (bytes/sec)
        disk_io = psutil.disk_io_counters()
        read_bps = (disk_io.read_bytes - self.last_disk_io.read_bytes) / dt if dt > 0 else 0
        write_bps = (disk_io.write_bytes - self.last_disk_io.write_bytes) / dt if dt > 0 else 0
        self.disk_io_history.append({"t": now, "v": round((read_bps + write_bps) / 1024 / 1024, 2)})  # MB/s
        self.last_disk_io = disk_io

        # Network I/O (bytes/sec)
        net_io = psutil.net_io_counters()
        sent_bps = (net_io.bytes_sent - self.last_net_io.bytes_sent) / dt if dt > 0 else 0
        recv_bps = (net_io.bytes_recv - self.last_net_io.bytes_recv) / dt if dt > 0 else 0
        self.net_io_history.append({"t": now, "v": round((sent_bps + recv_bps) / 1024 / 1024, 2)})  # MB/s
        self.last_net_io = net_io

        self.last_time = now
        return self.get_current()

    def get_current(self) -> dict:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        temp = None
        try:
            temps = psutil.sensors_temperatures()
            for name, entries in temps.items():
                if entries:
                    temp = entries[0].current
                    break
        except Exception:
            pass

        return {
            "cpu_percent": psutil.cpu_percent(interval=0),
            "cpu_count": psutil.cpu_count(),
            "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            "memory_total": mem.total,
            "memory_used": mem.used,
            "memory_percent": mem.percent,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "disk_percent": disk.percent,
            "net_sent": net.bytes_sent,
            "net_recv": net.bytes_recv,
            "temperature": temp,
            "uptime": time.time() - psutil.boot_time(),
        }

    def get_history(self) -> dict:
        return {
            "cpu": list(self.cpu_history),
            "memory": list(self.mem_history),
            "disk_io": list(self.disk_io_history),
            "net_io": list(self.net_io_history),
        }


monitor_svc = MonitorService()
