from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class VMTag(Base):
    """Color-coded labels for VMs, containers, and other resources."""
    __tablename__ = "vm_tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    color = Column(String, default="#f97316")  # hex color


class VMTagAssignment(Base):
    """Links tags to VMs/containers."""
    __tablename__ = "vm_tag_assignments"

    id = Column(Integer, primary_key=True, index=True)
    tag_id = Column(Integer, index=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer, index=True)


class ResourcePool(Base):
    """Resource pools to group VMs/containers for resource allocation."""
    __tablename__ = "resource_pools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    # CPU quotas
    cpu_quota = Column(Float, nullable=True)   # max total CPU cores
    cpu_limit = Column(Float, nullable=True)    # per-VM CPU limit
    # Memory quotas (MB)
    memory_quota = Column(Integer, nullable=True)  # max total memory
    memory_limit = Column(Integer, nullable=True)   # per-VM memory limit
    # Disk quotas (GB)
    disk_quota = Column(Float, nullable=True)   # max total disk
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class ResourcePoolMember(Base):
    """Members of a resource pool."""
    __tablename__ = "resource_pool_members"

    id = Column(Integer, primary_key=True, index=True)
    pool_id = Column(Integer, index=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer, index=True)


class LDAPConfig(Base):
    """LDAP / Active Directory integration configuration."""
    __tablename__ = "ldap_config"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=False)
    host = Column(String, default="")
    port = Column(Integer, default=636)
    use_tls = Column(Boolean, default=True)
    bind_dn = Column(String, default="")
    bind_password = Column(String, default="")
    base_dn = Column(String, default="")
    user_filter = Column(String, default="(objectClass=person)")
    group_filter = Column(String, default="(objectClass=group)")
    group_member_attr = Column(String, default="member")
    # Attribute mapping
    username_attr = Column(String, default="sAMAccountName")
    email_attr = Column(String, default="mail")
    # Role mapping
    admin_group = Column(String, default="Domain Admins")
    auditor_group = Column(String, default="Domain Users")
    created_at = Column(DateTime, server_default=func.now())


class ClientCertConfig(Base):
    """TLS client certificate configuration."""
    __tablename__ = "client_cert_config"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=False)
    ca_cert_path = Column(String, default="/etc/nexve/ca.crt")
    server_cert_path = Column(String, default="/etc/nexve/server.crt")
    server_key_path = Column(String, default="/etc/nexve/server.key")
    require_client_cert = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class NetworkSecurityGroup(Base):
    """Security groups: collections of firewall rules applied to VM interfaces."""
    __tablename__ = "network_security_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    comment = Column(String, default="")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class SecurityGroupRule(Base):
    """Rules within a security group."""
    __tablename__ = "security_group_rules"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, index=True)
    direction = Column(String, default="in")  # in, out
    action = Column(String, default="accept")  # accept, drop, reject
    protocol = Column(String, default="tcp")
    source = Column(String, default="")
    destination = Column(String, default="")
    sport = Column(String, default="")
    dport = Column(String, default="")
    comment = Column(String, default="")
    enabled = Column(Boolean, default=True)
    position = Column(Integer, default=0)


class SecurityGroupAssignment(Base):
    """Assigns security groups to VM/container interfaces."""
    __tablename__ = "security_group_assignments"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, index=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer, index=True)


class NetworkFirewallAlias(Base):
    """Firewall aliases: named groups of IPs/ports that can be referenced in rules."""
    __tablename__ = "network_firewall_aliases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    alias_type = Column(String, default="host")  # host, network, port
    comment = Column(String, default="")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class FirewallAliasEntry(Base):
    """Individual entries in a firewall alias."""
    __tablename__ = "firewall_alias_entries"

    id = Column(Integer, primary_key=True, index=True)
    alias_id = Column(Integer, index=True)
    value = Column(String)  # IP, CIDR, port, or port range


class NetworkRateLimit(Base):
    """Per-interface rate limiting."""
    __tablename__ = "network_rate_limits"

    id = Column(Integer, primary_key=True, index=True)
    interface = Column(String, index=True)
    rx_bytes = Column(Integer, nullable=True)   # bytes/sec ingress, null=unlimited
    tx_bytes = Column(Integer, nullable=True)   # bytes/sec egress, null=unlimited
    rx_burst = Column(Integer, nullable=True)
    tx_burst = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    credential_id = Column(Text, unique=True, nullable=False)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0)
    device_name = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    last_used = Column(DateTime, nullable=True)

class DatacenterFirewallRule(Base):
    __tablename__ = "datacenter_firewall_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, default="accept")  # accept, drop, reject
    direction = Column(String, default="in")  # in, out
    protocol = Column(String, default="tcp")  # tcp, udp, icmp, all
    source = Column(String, nullable=True)  # CIDR
    destination = Column(String, nullable=True)  # CIDR
    dport = Column(String, nullable=True)  # port or range
    comment = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    pos = Column(Integer, default=0)  # order
    created_at = Column(DateTime, server_default=func.now())

class DatacenterSettings(Base):
    __tablename__ = "datacenter_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, onupdate=func.now())

class MetricServer(Base):
    __tablename__ = "metric_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # influxdb, influxdb2, graphite
    host = Column(String, nullable=False)
    port = Column(Integer, default=8086)
    # InfluxDB v1
    database = Column(String, nullable=True)  # InfluxDB v1 database name
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    # InfluxDB v2
    organization = Column(String, nullable=True)
    token = Column(String, nullable=True)
    bucket = Column(String, nullable=True)
    # Graphite
    prefix = Column(String, nullable=True)
    # Common
    enabled = Column(Boolean, default=True)
    verify_ssl = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class RegisteredTag(Base):
    __tablename__ = "registered_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#00d4aa")  # hex color
    text_color = Column(String, nullable=True)  # optional text color
    description = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class LDAPDomainMapping(Base):
    __tablename__ = "ldap_domain_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    domain_group = Column(String, nullable=False)  # e.g. "cn=admins,dc=example,dc=com"
    nexve_role = Column(String, nullable=False)  # admin, auditor, user
    description = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class APITokenACL(Base):
    __tablename__ = "api_token_acl"
    
    id = Column(Integer, primary_key=True, index=True)
    token_id = Column(Integer, nullable=False, index=True)
    path = Column(String, nullable=False)  # e.g. "/vms", "/storage", "/nodes"
    roles = Column(String, default="PVEAuditor")  # comma-separated roles
    created_at = Column(DateTime, server_default=func.now())
