from sqlalchemy import create_engine
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
