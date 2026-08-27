from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use user-writable path for development, system path for production
_data_dir = os.path.join(os.path.dirname(__file__), "../../data")
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
