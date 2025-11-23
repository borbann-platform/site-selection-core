import logging
import os
import sys

# Add the parent directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shapely.geometry import Point
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.database import Base, settings
from src.models.db import Project, SavedSite

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_sites():
    logger.info("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Ensure tables exist
    Base.metadata.create_all(engine)

    # 1. Create or Get Demo Project
    project_name = "Bangkok Retail Expansion 2025"
    project = session.query(Project).filter_by(name=project_name).first()

    if not project:
        logger.info(f"Creating project: {project_name}")
        project = Project(
            name=project_name, description="Strategic expansion plan for Q1"
        )
        session.add(project)
        session.commit()
    else:
        logger.info(f"Using existing project: {project.id}")

    # 2. Create Seed Sites
    # We'll create a few sites with "real-looking" analysis data

    sites_data = [
        {
            "name": "Siam Square Flagship",
            "lat": 13.7445,
            "lon": 100.5342,
            "score": 95.5,
            "analysis": {
                "site_score": 95.5,
                "summary": {
                    "competitors_count": 12,
                    "magnets_count": 25,
                    "traffic_potential": "Very High",
                    "total_population": 15000,
                },
                "details": {
                    "nearby_competitors": ["Starbucks", "True Coffee", "Amazon"],
                    "nearby_magnets": [
                        "Siam Paragon",
                        "BTS Siam",
                        "Chulalongkorn Univ",
                    ],
                },
            },
        },
        {
            "name": "Ari Branch",
            "lat": 13.7835,
            "lon": 100.5450,
            "score": 82.0,
            "analysis": {
                "site_score": 82.0,
                "summary": {
                    "competitors_count": 5,
                    "magnets_count": 8,
                    "traffic_potential": "High",
                    "total_population": 22000,
                },
                "details": {
                    "nearby_competitors": ["Local Cafe", "Amazon"],
                    "nearby_magnets": ["BTS Ari", "La Villa"],
                },
            },
        },
    ]

    for site_info in sites_data:
        # Check if site exists (by name for simplicity in seed script)
        existing = (
            session.query(SavedSite)
            .filter_by(project_id=project.id, name=site_info["name"])
            .first()
        )
        if existing:
            logger.info(f"Site {site_info['name']} already exists. Skipping.")
            continue

        logger.info(f"Creating site: {site_info['name']}")

        # Create Geometry
        point = Point(site_info["lon"], site_info["lat"])
        # WKBElement for GeoAlchemy2
        # Note: In some setups, you might need WKTElement or direct WKB.
        # Using from_shape is cleaner if available, or WKTElement.
        from geoalchemy2.elements import WKTElement

        location_geom = WKTElement(point.wkt, srid=4326)

        new_site = SavedSite(
            project_id=project.id,
            name=site_info["name"],
            location=location_geom,
            score=site_info["score"],
            notes="Seeded by script",
            analysis_data=site_info["analysis"],
        )
        session.add(new_site)

    session.commit()
    logger.info("Seeding complete.")
    session.close()


if __name__ == "__main__":
    seed_sites()
