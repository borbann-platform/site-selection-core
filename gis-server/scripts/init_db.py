import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import Base, engine


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")


if __name__ == "__main__":
    init_db()
