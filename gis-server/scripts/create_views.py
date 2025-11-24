import logging
import os
import sys

from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import SessionLocal

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_views():
    db = SessionLocal()
    try:
        logger.info("Creating view_all_pois...")

        # Drop if exists
        db.execute(text("DROP VIEW IF EXISTS view_all_pois"))

        # Create view_all_pois
        sql_pois = """
        CREATE OR REPLACE VIEW view_all_pois AS
        SELECT 
            'school_' || id::text AS id,
            id::text as original_id,
            name,
            'school' AS type,
            'bma' AS source,
            geometry
        FROM schools
        UNION ALL
        SELECT 
            'police_' || id::text AS id,
            id::text as original_id,
            name,
            'police_station' AS type,
            'bma' AS source,
            geometry
        FROM police_stations
        UNION ALL
        SELECT 
            'museum_' || id::text AS id,
            id::text as original_id,
            name,
            'museum' AS type,
            'bma' AS source,
            geometry
        FROM museums
        UNION ALL
        SELECT 
            'gas_' || id::text AS id,
            id::text as original_id,
            name,
            'gas_station' AS type,
            'bma' AS source,
            geometry
        FROM gas_stations
        UNION ALL
        SELECT 
            'traffic_' || id::text AS id,
            id::text as original_id,
            name,
            'traffic_point' AS type,
            'bma' AS source,
            geometry
        FROM traffic_points
        UNION ALL
        SELECT 
            'water_' || md5(name || address) AS id,
            name as original_id,
            name,
            'water_transport' AS type,
            'bma' AS source,
            geometry
        FROM water_transport_piers
        UNION ALL
        SELECT 
            'tourist_' || id::text AS id,
            id::text as original_id,
            name,
            'tourist_attraction' AS type,
            'bma' AS source,
            geometry
        FROM tourist_attractions
        UNION ALL
        SELECT 
            'bus_shelter_' || COALESCE(contract_number, 'unknown') || '_' || COALESCE(code_shelter, 'unknown') AS id,
            contract_number as original_id,
            location_name as name,
            'bus_shelter' AS type,
            'bma' AS source,
            geometry
        FROM bus_shelters
        UNION ALL
        SELECT 
            'transit_' || stop_id AS id,
            stop_id as original_id,
            stop_name as name,
            'transit_stop' AS type,
            COALESCE(source, 'gtfs') AS source,
            geometry
        FROM transit_stops
        UNION ALL
        SELECT 
            'contributed_' || id::text AS id,
            id::text as original_id,
            name_th as name,
            poi_type as type,
            'contributed' AS source,
            geometry
        FROM contributed_pois;
        """

        db.execute(text(sql_pois))
        logger.info("view_all_pois created successfully.")

        logger.info("Creating view_residential_supply...")

        # Drop if exists
        db.execute(text("DROP VIEW IF EXISTS view_residential_supply"))

        sql_residential = """
        CREATE OR REPLACE VIEW view_residential_supply AS
        SELECT 
            'condo_' || id::text AS id,
            id::text as original_id,
            name,
            'condo_project' AS type,
            price_sale AS price,
            'hipflat' AS source,
            geometry
        FROM condo_projects
        UNION ALL
        SELECT 
            'listing_' || id::text AS id,
            id::text as original_id,
            title AS name,
            'listing' AS type,
            price,
            'bania' AS source,
            geometry
        FROM real_estate_listings;
        """

        db.execute(text(sql_residential))
        logger.info("view_residential_supply created successfully.")

        db.commit()

    except Exception as e:
        logger.error(f"Error creating views: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_views()
