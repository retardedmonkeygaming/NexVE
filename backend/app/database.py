from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database lives in /var/lib/nexve in production, fallback to source tree in dev
_prod_dir = "/var/lib/nexve"
_dev_dir = os.path.join(os.path.dirname(__file__), "../../data")

if os.path.isdir("/opt/nexve") or os.path.isdir(_prod_dir):
    _data_dir = _prod_dir
else:
    _data_dir = _dev_dir

os.makedirs(_data_dir, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(_data_dir, 'nexve.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_database():
    """Auto-migrate: add missing columns to existing tables."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Define new columns per table: {table_name: [(col_name, col_def_sql), ...]}
    migrations = {
        "vms": [
            ("tpm_enabled", "BOOLEAN DEFAULT 0"),
            ("tpm_version", "VARCHAR DEFAULT 'v2.0'"),
            ("secure_boot", "BOOLEAN DEFAULT 0"),
            ("uefi_disk", "VARCHAR"),
            ("scsi_hw", "VARCHAR DEFAULT 'virtio-scsi-single'"),
            ("cpu_sockets", "INTEGER DEFAULT 1"),
            ("cpu_cores", "INTEGER"),
            ("cpu_threads", "INTEGER DEFAULT 1"),
            ("numa", "BOOLEAN DEFAULT 0"),
            ("hugepages", "VARCHAR DEFAULT 'none'"),
            ("virtio_iso", "VARCHAR"),
            ("cloud_init", "BOOLEAN DEFAULT 0"),
            ("cloud_init_user", "VARCHAR"),
            ("cloud_init_sshkey", "TEXT"),
            ("cloud_init_ip", "VARCHAR"),
            ("cloud_init_gateway", "VARCHAR"),
            ("cloud_init_dns", "VARCHAR"),
            ("extra_disks", "TEXT"),
            ("extra_nics", "TEXT"),
            ("passthrough_pci", "TEXT"),
            ("passthrough_usb", "TEXT"),
            ("cpu_units", "INTEGER DEFAULT 1024"),
            ("cpu_limit", "FLOAT"),
            ("memory_min", "INTEGER"),
            ("vga_display", "VARCHAR DEFAULT 'std'"),
            ("vga_memory", "INTEGER"),
            ("watchdog_model", "VARCHAR"),
            ("disk_cache", "VARCHAR DEFAULT 'none'"),
            ("disk_discard", "BOOLEAN DEFAULT 0"),
            ("disk_iothread", "BOOLEAN DEFAULT 0"),
            ("disk_ssd", "BOOLEAN DEFAULT 0"),
            ("efidisk_size", "INTEGER"),
            ("cpu_affinity", "VARCHAR"),
        ],
        "containers": [
            ("dns_servers", "VARCHAR"),
            ("gateway", "VARCHAR"),
            ("mac_address", "VARCHAR"),
            ("mtu", "INTEGER DEFAULT 1500"),
            ("cpu_quota", "INTEGER"),
            ("cpu_period", "INTEGER DEFAULT 100000"),
            ("cpu_nice", "INTEGER DEFAULT 0"),
            ("ssh_keys", "TEXT"),
            ("password_hash", "VARCHAR"),
            ("seccomp_profile", "VARCHAR"),
        ],
    }

    with engine.connect() as conn:
        for table_name, columns in migrations.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for col_name, col_def in columns:
                if col_name not in existing_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))
                        conn.commit()
                    except Exception:
                        pass  # Column may already exist in concurrent access
