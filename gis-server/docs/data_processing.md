# Data Processing Documentation

This document outlines the data sources available in the `data/` directory and their processing status.

## Data Inventory

| File Name | Description | Status | Processing Notes |
| :--- | :--- | :--- | :--- |
| `bangkok-population.csv` | Population data with grid geometry | **Usable** | Contains `WKT` (MULTIPOLYGON) and `GRID_LON`/`GRID_LAT`. Can be loaded directly into PostGIS. |
| `bus-shelter.csv` | Bus shelter locations | **Usable** | Contains `coordinates` column as a string `"[lat, lon]"`. Needs parsing to extract lat/lon. |
| `china-town-data.csv` | Points of interest in China Town | **Usable** | Contains `latitude` and `longitude` columns. |
| `flood-warning.csv` | Flood risk areas | **Needs Geocoding** | Contains `District` and `area` description (e.g., road names). No coordinates. **Marked as unused for now.** |
| `gasstation.csv` | Gas station locations | **Usable** | Contains `lat` and `lng` columns. |
| `local_museum.csv` | Local museums | **Usable** | Contains `lat` and `lng` columns. |
| `police_station.csv` | Police stations | **Usable** | Contains `lat` and `lng` columns. |
| `school-bma.csv` | BMA Schools | **Usable** | Contains `LATITUDE` and `LONGITUDE` columns. |
| `traffic-manage.csv` | Traffic management points | **Usable** | Contains `latitude` and `longitude` columns. |
| `water-transportation.csv` | Water transportation piers | **Usable** | Contains `latitude` and `longitude` columns. |
| `Bangkok.osm.geojson` | OpenStreetMap data for Bangkok | **Usable** | Standard GeoJSON format. |
| `bangkok-gtfs/` | GTFS public transit feed | **Usable** | Standard GTFS format. `stops.txt` contains stop coordinates. |
| `bania-scrape/` | Real estate listings (CSV) | **Usable** | Contains `latitude` and `longitude`. Multiple files (`apartment_all.csv`, etc.). |
| `hipflat-scrape/` | Condo projects (JSON) | **Usable** | JSON format with `latitude` and `longitude`. |
| `longdomap-bus-gtfs/` | Additional GTFS feed | **Usable** | Standard GTFS format. |
| `longdomap-contributed-pois.csv` | User-contributed POIs | **Usable** | Large CSV (>50MB). Contains `latitude` and `longitude`. |

## Processing Instructions

### Usable Data
Most CSV files can be processed by reading the latitude and longitude columns and converting them into GeoJSON or inserting them into a PostGIS database as `Geometry(Point, 4326)`.

- **Bus Shelters**: Parse the `coordinates` string to get lat/lon.
- **Population**: Use `WKT` to create Polygon geometries.
- **Real Estate**:
    - **Bania**: CSVs with standard lat/lon.
    - **Hipflat**: JSON with lat/lon.
- **Contributed POIs**: Large CSV, processed in chunks or streamed.

### Unusable Data (Needs Geocoding)
- **Flood Warning**: Requires a geocoding service (e.g., Google Maps API, Nominatim) to convert the `area` description into a line or polygon geometry. Currently skipped.

## Database Initialization
See `scripts/` directory for loading scripts.

### Running the ETL Pipeline

1.  **Initialize Database**:
    ```bash
    uv run scripts/init_db.py
    ```
    This creates all tables defined in `src/models/`.

2.  **Load All Data**:
    ```bash
    uv run scripts/etl/load_all.py
    ```
    This script runs the individual loaders for Places, Transit, Population, Real Estate, and Contributed POIs.

### Individual Loaders
*   `scripts/etl/load_places.py`: Loads CSVs into `bus_shelters`, `schools`, `police_stations`, etc.
*   `scripts/etl/load_gtfs.py`: Loads GTFS stops and shapes from multiple sources (`bangkok-gtfs`, `longdomap-bus-gtfs`).
*   `scripts/etl/load_population.py`: Loads population grid.
*   `scripts/etl/load_realestate.py`: Loads Bania (CSV) and Hipflat (JSON) data.
*   `scripts/etl/load_contributed_pois.py`: Loads large contributed POI dataset.

