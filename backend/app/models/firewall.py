from sqlalchemy import Column, Integer, String, Boolean
from ..database import Base

class FirewallRule(Base):
    __tablename__ = "firewall_rules"

    id = Column(Integer, primary_key=True, index=True)
    direction = Column(String)  # in / out
    action = Column(String)  # accept / drop / reject
    protocol = Column(String, default="tcp")  # tcp, udp, icmp, all
    source = Column(String, default="")  # IP/CIDR or empty for any
    destination = Column(String, default="")
    dport = Column(String, default="")  # port or range like 80,443 or 1000:2000
    sport = Column(String, default="")
    comment = Column(String, default="")
    enabled = Column(Boolean, default=True)

    # Target: "host", or "vm:{vm_id}", or "group:{group_name}"
    target_type = Column(String, default="host")
    target_id = Column(String, default="")
    log = Column(Boolean, default=False)
    position = Column(Integer, default=0)


class FirewallGroup(Base):
    __tablename__ = "firewall_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    comment = Column(String, default="")
