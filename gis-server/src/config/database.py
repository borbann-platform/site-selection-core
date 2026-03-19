import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import settings

logger = logging.getLogger(__name__)


_connect_args: dict[str, str] = {}
if settings.DATABASE_URL.startswith("postgresql"):
    # Set statement timeout at connection level without forcing a checkout in
    # dependency setup for every request.
    _connect_args["options"] = (
        f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"
    )

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


logger.info("Database module loaded")


def get_db_session():
    """
    FastAPI dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
