from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class VM(Base):
    __tablename__ = "vms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="stopped")
    vcpu = Column(Integer, default=2)
    cpu_type = Column(String, default="host")  # host, qemu64, kvm64, etc.
    memory_mb = Column(Integer, default=2048)
    disk_gb = Column(Integer, default=50)
    disk_interface = Column(String, default="virtio")  # virtio, scsi, ide, sata
    os_type = Column(String, default="linux")
    machine_type = Column(String, default="q35")  # q35, i440fx
    bios_type = Column(String, default="seabios")  # seabios, ovmf (UEFI)
    boot_order = Column(String, default="c")  # c=cdrom, d=disk, n=network
    ip_address = Column(String, nullable=True)
    mac_address = Column(String, nullable=True)
    notes = Column(Text, nullable=True, default="")
    serial_console = Column(Boolean, default=False)
    agent_enabled = Column(Boolean, default=True)  # QEMU guest agent
    balloon = Column(Boolean, default=False)  # Memory ballooning
    hotplug_cpu = Column(Boolean, default=False)
    hotplug_ram = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False)
    linked_from = Column(Integer, nullable=True)  # parent VM id for linked clones
    created_at = Column(DateTime, server_default=func.now())
    last_started = Column(DateTime, nullable=True)


class Container(Base):
    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="stopped")
    vcpu = Column(Integer, default=1)
    memory_mb = Column(Integer, default=512)
    swap_mb = Column(Integer, default=512)
    disk_gb = Column(Integer, default=8)
    template = Column(String, default="debian-12-standard")
    ip_address = Column(String, nullable=True)
    hostname = Column(String, nullable=True)
    unprivileged = Column(Boolean, default=True)
    nesting = Column(Boolean, default=False)
    mount_points = Column(Text, nullable=True)  # JSON: [{"volume": "...", "mp": "..."}]
    cpu_weight = Column(Integer, default=100)
    io_priority = Column(String, default="normal")  # low, normal, high
    net_rate = Column(Integer, nullable=True)  # KB/s limit, null=unlimited
    startup_order = Column(Integer, default=0)
    shutdown_order = Column(Integer, default=0)
    notes = Column(Text, nullable=True, default="")
    created_at = Column(DateTime, server_default=func.now())


class BackupSchedule(Base):
    __tablename__ = "backup_schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer)
    cron_expr = Column(String)  # "0 2 * * *" = daily at 2am
    retention_days = Column(Integer, default=30)
    max_backups = Column(Integer, default=7)
    storage_path = Column(String, default="/opt/nexve/data/backups")
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    token_hash = Column(String, unique=True)
    user_id = Column(Integer)
    permissions = Column(String, default="read")  # read, write, admin
    expires_at = Column(DateTime, nullable=True)
    last_used = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

