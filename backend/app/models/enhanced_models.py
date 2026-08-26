"""
NexVE Enhanced Models v3.0
Models for live migration, HA, clustering, SDN, Ceph, ACME,
notifications, SSL/TLS, settings, and enhanced backups.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from ..database import Base


# ═══════════════════════════════════════════════════════════════
# Live Migration
# ═══════════════════════════════════════════════════════════════

class MigrationJob(Base):
    """Tracks VM/container live migration jobs."""
    __tablename__ = "migration_jobs"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer)
    target_name = Column(String, nullable=True)
    source_node = Column(String)
    target_node = Column(String)
    status = Column(String, default="pending")  # pending, running, completed, failed
    progress = Column(Float, default=0.0)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════════
# High Availability
# ═══════════════════════════════════════════════════════════════

class HAGroup(Base):
    """HA failover groups for clustering."""
    __tablename__ = "ha_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    nodes = Column(Text, nullable=True)  # JSON list of node names
    strategy = Column(String, default="failover")  # failover, migrate
    max_restart = Column(Integer, default=3)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class HAGuest(Base):
    """Guests managed by HA."""
    __tablename__ = "ha_guests"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer)
    target_name = Column(String, nullable=True)
    group_id = Column(Integer, nullable=True)
    state = Column(String, default="active")  # active, stopped, error
    priority = Column(Integer, default=0)
    max_restart = Column(Integer, default=3)
    current_node = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Clustering
# ═══════════════════════════════════════════════════════════════

class ClusterNode(Base):
    """Nodes in the cluster."""
    __tablename__ = "cluster_nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    address = Column(String)
    status = Column(String, default="online")  # online, offline, maintenance
    node_id = Column(Integer, nullable=True)  # Corosync node ID
    join_date = Column(DateTime, server_default=func.now())
    last_seen = Column(DateTime, nullable=True)


class ClusterConfig(Base):
    """Cluster-wide configuration key-value pairs."""
    __tablename__ = "cluster_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ═══════════════════════════════════════════════════════════════
# SDN (Software-Defined Networking)
# ═══════════════════════════════════════════════════════════════

class SDNZone(Base):
    """SDN zones — network isolation domains."""
    __tablename__ = "sdn_zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    zone_type = Column(String, default="simple")  # simple, vxlan, qinq, vlan
    bridge = Column(String, nullable=True)
    mtu = Column(Integer, default=1500)
    enabled = Column(Boolean, default=True)
    config_json = Column(Text, nullable=True)  # Extra zone config
    created_at = Column(DateTime, server_default=func.now())


class SDNVnet(Base):
    """Virtual networks within SDN zones."""
    __tablename__ = "sdn_vnets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    zone_id = Column(Integer, index=True)
    zone_name = Column(String, nullable=True)
    vlan_id = Column(Integer, nullable=True)
    bridge = Column(String, nullable=True)
    cidr = Column(String, nullable=True)  # e.g. 10.0.0.0/24
    gateway = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Ceph
# ═══════════════════════════════════════════════════════════════

class CephConfig(Base):
    """Ceph cluster configuration."""
    __tablename__ = "ceph_config"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=False)
    cluster_name = Column(String, default="ceph")
    fsid = Column(String, nullable=True)
    mon_host = Column(String, nullable=True)  # Comma-separated monitor hosts
    auth_type = Column(String, default="cephx")
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# ACME / Let's Encrypt
# ═══════════════════════════════════════════════════════════════

class SSLCertificate(Base):
    """SSL/TLS certificates managed by NexVE."""
    __tablename__ = "ssl_certificates"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True)
    cert_path = Column(String)
    key_path = Column(String)
    ca_path = Column(String, nullable=True)
    issuer = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, default=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class ACMEAccount(Base):
    """ACME/Let's Encrypt account configuration."""
    __tablename__ = "acme_accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String)
    provider = Column(String, default="letsencrypt")  # letsencrypt, zerossl, buypass
    account_uri = Column(String, nullable=True)
    private_key_path = Column(String, nullable=True)
    challenge_type = Column(String, default="http")  # http, dns
    dns_provider = Column(String, nullable=True)  # cloudflare, route53, etc.
    dns_config_json = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Enhanced Backups
# ═══════════════════════════════════════════════════════════════

class BackupRecord(Base):
    """Detailed backup records with checksums and metadata."""
    __tablename__ = "backup_records"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, nullable=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer)
    target_name = Column(String, nullable=True)
    path = Column(String)
    filename = Column(String)
    size_bytes = Column(Integer, default=0)
    checksum = Column(String, nullable=True)  # SHA256
    encrypted = Column(Boolean, default=False)
    encryption_key_id = Column(String, nullable=True)
    incremental = Column(Boolean, default=False)
    parent_backup_id = Column(Integer, nullable=True)
    status = Column(String, default="completed")  # running, completed, failed, verified
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)


class BackupRemote(Base):
    """Remote backup targets (NFS, S3, etc.)."""
    __tablename__ = "backup_remotes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    remote_type = Column(String)  # nfs, s3, sftp, local
    host = Column(String, nullable=True)
    path = Column(String)
    username = Column(String, nullable=True)
    password_encrypted = Column(String, nullable=True)
    bucket = Column(String, nullable=True)  # For S3
    region = Column(String, nullable=True)  # For S3
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Notification Targets
# ═══════════════════════════════════════════════════════════════

class NotificationTarget(Base):
    """Notification delivery targets (email, webhook, Slack, etc.)."""
    __tablename__ = "notification_targets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    target_type = Column(String)  # email, webhook, slack, discord, telegram
    config_json = Column(Text)  # Type-specific configuration
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class NotificationRule(Base):
    """Rules for when to send notifications."""
    __tablename__ = "notification_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    target_id = Column(Integer)  # Which notification target to use
    event_types = Column(Text)  # JSON list: ["vm.created", "backup.failed", "disk.health"]
    severity = Column(String, default="warning")  # info, warning, error, critical
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# System Settings (for import/export/rollback)
# ═══════════════════════════════════════════════════════════════

class SystemSetting(Base):
    """Key-value settings with categories for import/export/rollback."""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text)
    category = Column(String, default="general")  # general, network, security, storage, backup
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String, nullable=True)


class SettingsHistory(Base):
    """Previous settings values for rollback."""
    __tablename__ = "settings_history"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, index=True)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(String, nullable=True)
    changed_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# User SSH Keys
# ═══════════════════════════════════════════════════════════════

class UserSSHKey(Base):
    """SSH public keys for users."""
    __tablename__ = "user_ssh_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    username = Column(String, nullable=True)
    name = Column(String)  # Label for the key
    public_key = Column(Text)
    fingerprint = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# User Quotas
# ═══════════════════════════════════════════════════════════════

class UserQuota(Base):
    """Resource quotas per user."""
    __tablename__ = "user_quotas"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)
    max_vms = Column(Integer, nullable=True)  # null = unlimited
    max_containers = Column(Integer, nullable=True)
    max_cpu_cores = Column(Integer, nullable=True)
    max_memory_gb = Column(Integer, nullable=True)
    max_storage_gb = Column(Integer, nullable=True)
    max_backups = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Active Sessions (for management)
# ═══════════════════════════════════════════════════════════════

class UserSession(Base):
    """Active user sessions for management."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    username = Column(String, nullable=True)
    token_hash = Column(String, unique=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)
    last_activity = Column(DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════════
# Storage Tiering
# ═══════════════════════════════════════════════════════════════

class StorageTier(Base):
    """Storage tiering classification."""
    __tablename__ = "storage_tiers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    tier_type = Column(String)  # hot, warm, cold
    storage_names = Column(Text)  # JSON list of storage backend names
    max_iops = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Firewall Statistics
# ═══════════════════════════════════════════════════════════════

class FirewallStats(Base):
    """Firewall rule statistics (packet counts)."""
    __tablename__ = "firewall_stats"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, index=True)
    packets_matched = Column(Integer, default=0)
    bytes_matched = Column(Integer, default=0)
    last_matched = Column(DateTime, nullable=True)
    collected_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Per-VM Firewall Rules
# ═══════════════════════════════════════════════════════════════

class VMFirewallRule(Base):
    """Firewall rules applied to specific VMs/containers."""
    __tablename__ = "vm_firewall_rules"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String)  # vm, container
    target_id = Column(Integer)
    direction = Column(String)  # in, out
    action = Column(String)  # accept, drop, reject
    protocol = Column(String, default="tcp")
    source = Column(String, default="")
    destination = Column(String, default="")
    sport = Column(String, default="")
    dport = Column(String, default="")
    comment = Column(String, default="")
    log = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# Firewall Macros (predefined rules)
# ═══════════════════════════════════════════════════════════════

class FirewallMacro(Base):
    """Predefined firewall rule macros."""
    __tablename__ = "firewall_macros"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    protocol = Column(String, default="tcp")
    dport = Column(String)
    direction = Column(String, default="in")
    action = Column(String, default="accept")
