from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from ..database import Base


class VM(Base):
    __tablename__ = "vms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="stopped")
    vcpu = Column(Integer, default=2)
    memory_mb = Column(Integer, default=2048)
    disk_gb = Column(Integer, default=50)
    os_type = Column(String, default="linux")
    ip_address = Column(String, nullable=True)
    mac_address = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    last_started = Column(DateTime, nullable=True)


class Container(Base):
    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(String, default="stopped")
    vcpu = Column(Integer, default=1)
    memory_mb = Column(Integer, default=512)
    disk_gb = Column(Integer, default=8)
    template = Column(String, default="debian-12-standard")
    ip_address = Column(String, nullable=True)
    bridge = Column(String, default="vmbr0")
    created_at = Column(DateTime, server_default=func.now())
