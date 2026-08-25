from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from ..database import Base


class Storage(Base):
    __tablename__ = "storage"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(String)  # directory, lvm, zfs, nfs, cifs, iscsi
    path = Column(String, nullable=True)  # for directory type
    vg_name = Column(String, nullable=True)  # for LVM
    pool_name = Column(String, nullable=True)  # for ZFS
    remote_path = Column(String, nullable=True)  # for NFS/CIFS
    remote_host = Column(String, nullable=True)
    content_types = Column(String, default="images,rootdir")  # images=VM disks, rootdir=containers
    enabled = Column(Boolean, default=True)
    total_gb = Column(Float, default=0)
    used_gb = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
