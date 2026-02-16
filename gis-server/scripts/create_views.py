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
        logger.info("Creating materialized view mat_all_pois...")

        # Drop materialized view if exists (different syntax than regular view)
        db.execute(text("DROP MATERIALIZED VIEW IF EXISTS mat_all_pois CASCADE"))
        # Also drop legacy regular view if it exists
        db.execute(text("DROP VIEW IF EXISTS view_all_pois CASCADE"))

        # Create mat_all_pois as MATERIALIZED VIEW for better performance
        sql_pois = """
        CREATE MATERIALIZED VIEW mat_all_pois AS
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
        FROM contributed_pois
        UNION ALL
        SELECT 
            'osm_' || id::text AS id,
            osm_id as original_id,
            COALESCE(name, name_th, name_en) as name,
            poi_type as type,
            'osm_thailand' AS source,
            geometry
        FROM osm_pois
        WHERE is_duplicate = FALSE;
        """

        db.execute(text(sql_pois))
        logger.info("mat_all_pois materialized view created successfully.")

        # Create spatial index on materialized view for fast tile queries
        logger.info("Creating spatial index on mat_all_pois...")
        db.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_mat_all_pois_geometry 
            ON mat_all_pois USING GIST (geometry)
        """)
        )
        logger.info("Spatial index on mat_all_pois created successfully.")

        # Create backward-compatible view alias pointing to materialized view
        logger.info("Creating view_all_pois alias...")
        db.execute(text("DROP VIEW IF EXISTS view_all_pois CASCADE"))
        db.execute(
            text("""
            CREATE OR REPLACE VIEW view_all_pois AS 
            SELECT * FROM mat_all_pois
        """)
        )
        logger.info("view_all_pois alias created successfully.")

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
        FROM real_estate_listings
        UNION ALL
        SELECT
            'scraped_' || id::text AS id,
            source || ':' || source_listing_id AS original_id,
            COALESCE(title, title_en, title_th) AS name,
            COALESCE(property_type, 'scraped_project') AS type,
            COALESCE(price_start, price_end)::text AS price,
            source,
            geometry
        FROM scraped_listings
        UNION ALL
        SELECT 
            'house_' || id::text AS id,
            id::text as original_id,
            COALESCE(village, amphur || ' ' || building_style_desc) AS name,
            building_style_desc AS type,
            total_price::text AS price,
            'treasury' AS source,
            geometry
        FROM house_prices;
        """

        db.execute(text(sql_residential))
        logger.info("view_residential_supply created successfully.")

        # Create view_transit_lines - joins shapes with route metadata
        logger.info("Creating view_transit_lines...")
        db.execute(text("DROP VIEW IF EXISTS view_transit_lines"))

        sql_transit_lines = """
        CREATE OR REPLACE VIEW view_transit_lines AS
        SELECT DISTINCT ON (s.shape_id)
            s.shape_id,
            r.route_id,
            r.route_short_name,
            r.route_long_name,
            r.route_type,
            r.route_color,
            r.agency_id,
            s.geometry
        FROM transit_shapes s
        JOIN transit_trips t ON s.shape_id = t.shape_id
        JOIN transit_routes r ON t.route_id = r.route_id
        ORDER BY s.shape_id, r.route_type;
        """

        db.execute(text(sql_transit_lines))
        logger.info("view_transit_lines created successfully.")

        db.commit()

    except Exception as e:
        logger.error(f"Error creating views: {e}")
        db.rollback()
    finally:
        db.close()


def refresh_materialized_views():
    """Refresh all materialized views. Call this after data updates."""
    db = SessionLocal()
    try:
        logger.info("Refreshing mat_all_pois materialized view...")
        # CONCURRENTLY allows reads during refresh (requires unique index)
        # Using regular refresh since we don't have unique index
        db.execute(text("REFRESH MATERIALIZED VIEW mat_all_pois"))
        db.commit()
        logger.info("mat_all_pois refreshed successfully.")
        return True
    except Exception as e:
        logger.error(f"Error refreshing materialized views: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    create_views()
