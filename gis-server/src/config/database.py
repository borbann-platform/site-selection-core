from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .settings import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_session():
    """
    FastAPI dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
