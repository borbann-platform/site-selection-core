import logging
import os
import sys

# Add parent directory to path to import from src
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import geopandas as gpd
import pandas as pd
from shapely import wkt
from sqlalchemy import create_engine, text
from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuration ---
DATABASE_URL = settings.DATABASE_URL
CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "bangkok-population.csv"
)
TABLE_NAME = "demographics"
CHUNK_SIZE = 1000


def load_demographics():
    logging.info("Starting demographics loading process...")

    if not os.path.exists(CSV_PATH):
        logging.error(f"File not found: {CSV_PATH}")
        return

    try:
        # 1. Read CSV
        logging.info(f"Reading CSV file from: {CSV_PATH}")
        df = pd.read_csv(CSV_PATH)

        # 2. Convert WKT to Geometry
        logging.info("Converting WKT to geometry...")
        df["geometry"] = df["WKT"].apply(wkt.loads)

        # 3. Create GeoDataFrame
        gdf = gpd.GeoDataFrame(df, geometry="geometry")

        # 4. Set CRS (Assuming EPSG:32647 - UTM Zone 47N for Bangkok)
        # The coordinates 648535, 1521771 are definitely UTM.
        gdf.set_crs(epsg=32647, inplace=True)

        # 5. Reproject to EPSG:4326 (Lat/Lon)
        logging.info("Reprojecting to EPSG:4326...")
        gdf.to_crs(epsg=4326, inplace=True)

        # 6. Rename and Select Columns
        # Min_Pop/RA -> population_density
        gdf.rename(
            columns={"Min_Pop/RA": "population_density", "id": "grid_id"}, inplace=True
        )
        gdf = gdf[["grid_id", "population_density", "geometry"]]

        logging.info(f"Processed {len(gdf)} demographic grids.")

        # 7. Connect to DB and Load
        logging.info("Connecting to the database...")
        engine = create_engine(DATABASE_URL)

        # Use GeoDataFrame's to_postgis method
        logging.info(f"Writing to table '{TABLE_NAME}'...")
        gdf.to_postgis(
            name=TABLE_NAME,
            con=engine,
            if_exists="replace",
            index=False,
            chunksize=CHUNK_SIZE,
        )

        logging.info(f"Successfully loaded data into '{TABLE_NAME}'.")

        # Verify
        with engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar()
            logging.info(
                f"Verification: Table '{TABLE_NAME}' now contains {count} rows."
            )

    except Exception as e:
        logging.exception(f"An error occurred: {e}")


if __name__ == "__main__":
    load_demographics()
