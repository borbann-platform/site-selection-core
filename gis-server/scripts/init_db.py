import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import Base, engine
from src.models.demographics import *  # noqa

# Import all models to ensure they are registered with Base.metadata
from src.models.places import *  # noqa
from src.models.realestate import *  # noqa
from src.models.transit import *  # noqa


def init_db():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating database tables...")
    print(f"Registered tables: {Base.metadata.tables.keys()}")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")


if __name__ == "__main__":
    init_db()
