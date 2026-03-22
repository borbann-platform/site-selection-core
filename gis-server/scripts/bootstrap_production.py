import logging
import sys
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.create_user_properties_table import create_user_properties_table
from scripts.create_views import create_views
from src import models  # noqa: F401
from src.config.database import Base, engine
from src.models.demographics import *  # noqa: F401,F403
from src.models.places import *  # noqa: F401,F403
from src.models.realestate import *  # noqa: F401,F403
from src.models.transit import *  # noqa: F401,F403

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _ensure_extension(name: str, *, required: bool) -> None:
    statement = text(f"CREATE EXTENSION IF NOT EXISTS {name}")
    try:
        with engine.begin() as conn:
            conn.execute(statement)
    except Exception as exc:
        message = f"Unable to enable extension '{name}': {exc}"
        if required:
            raise RuntimeError(message) from exc
        logger.warning("%s", message)
    else:
        logger.info("Extension ready: %s", name)


def bootstrap_production() -> None:
    logger.info("Ensuring database extensions")
    _ensure_extension("postgis", required=True)
    _ensure_extension("pgcrypto", required=True)
    _ensure_extension("vector", required=False)

    logger.info("Creating SQLAlchemy-managed tables")
    Base.metadata.create_all(bind=engine)

    logger.info("Ensuring supplemental tables")
    create_user_properties_table()

    logger.info("Ensuring materialized and helper views")
    create_views()

    logger.info("Production bootstrap complete")


if __name__ == "__main__":
    bootstrap_production()
