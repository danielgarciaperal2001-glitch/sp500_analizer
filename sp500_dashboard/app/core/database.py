from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
from typing import Generator

# Engine MySQL
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ✅ FIX: Función generator CORRECTA para FastAPI Depends
def get_db() -> Generator:
    """✅ Dependencia FastAPI: Session por request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
