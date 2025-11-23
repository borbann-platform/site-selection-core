import logging
import os

import geopandas as gpd
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuration ---
# It's better to load this from environment variables or a config file in a real app
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/gisdb"
)
GEOJSON_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "Bangkok.osm.geojson"
)
TABLE_NAME = "pois"
CHUNK_SIZE = 1000  # Number of rows to insert at a time


# --- Main Data Loading Function ---
def load_data_to_postgis():
    """
    Reads GeoJSON data, processes it, and loads it into a PostGIS table.
    """
    logging.info("Starting data loading process...")

    try:
        # 1. Read the GeoJSON file into a GeoDataFrame
        logging.info(f"Reading GeoJSON file from: {GEOJSON_PATH}")
        gdf = gpd.read_file(GEOJSON_PATH)
        logging.info(f"Successfully read {len(gdf)} features.")

        # 2. Data Cleaning and Transformation
        # Keep only necessary columns and rename them for clarity
        gdf = gdf[["amenity", "name", "geometry"]].copy()

        # Drop rows where 'amenity' or 'geometry' is missing
        gdf.dropna(subset=["amenity", "geometry"], inplace=True)

        # Ensure all geometries are valid Points
        gdf = gdf[gdf.geometry.type == "Point"]

        # Reset index
        gdf.reset_index(drop=True, inplace=True)

        logging.info(f"Processed data, resulting in {len(gdf)} valid Point features.")
        if gdf.empty:
            logging.warning("No data to load after processing. Exiting.")
            return

        # 3. Connect to the database and load the data
        logging.info("Connecting to the database...")
        engine = create_engine(DATABASE_URL)

        with engine.connect() as conn:
            logging.info("Connection successful.")
            # Check if the table already exists and handle it
            # For this script, we'll replace it. In production, you might append or update.
            logging.info(f"Writing {len(gdf)} features to table '{TABLE_NAME}'...")

            # Use GeoDataFrame's to_postgis method
            gdf.to_postgis(
                name=TABLE_NAME,
                con=engine,
                if_exists="replace",  # Replace the table if it already exists
                index=False,
                chunksize=CHUNK_SIZE,
                # The geometry column type will be automatically detected
            )

            logging.info(f"Successfully loaded data into '{TABLE_NAME}'.")

            # Verify the number of rows
            count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar()
            logging.info(
                f"Verification: Table '{TABLE_NAME}' now contains {count} rows."
            )

    except FileNotFoundError:
        logging.exception(f"Error: The file was not found at {GEOJSON_PATH}")
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    load_data_to_postgis()
