from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from ..database import Base

class ISOImage(Base):
    __tablename__ = "iso_images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    filename = Column(String)
    size_gb = Column(Float)
    os_type = Column(String, default="linux")  # linux, windows, other
    url = Column(String, nullable=True)
    downloaded = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
