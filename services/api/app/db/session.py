from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True,)
# Future: tune SQLAlchemy pool_size/max_overflow based on deployment concurrency and Postgres connection limits.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]: 
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()