# Data Dictionary

This document describes the database schema for the GIS Server.

## Places (POIs)

### `bus_shelters`
*   **Source**: `bus-shelter.csv`
*   **Description**: Locations of bus shelters.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `contract_number`: String
    *   `project_name`: String
    *   `location_name`: String
    *   `code_shelter`: String
    *   `asset_code`: String
    *   `district`: String
    *   `shelter_type`: String
    *   `status`: String
    *   `geometry`: Point (4326)

### `schools`
*   **Source**: `school-bma.csv`
*   **Description**: BMA Schools.
*   **Columns**:
    *   `id`: String (PK, IDSCHOOL)
    *   `name`: String
    *   `address`: Text
    *   `district`: String
    *   `subdistrict`: String
    *   `level`: String
    *   `phone`: String
    *   `geometry`: Point (4326)

### `police_stations`
*   **Source**: `police_station.csv`
*   **Description**: Police stations.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `name`: String
    *   `address`: Text
    *   `phone`: String
    *   `district`: String
    *   `division`: String
    *   `geometry`: Point (4326)

### `museums`
*   **Source**: `local_museum.csv`
*   **Description**: Local museums.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `name`: String
    *   `district`: String
    *   `address`: Text
    *   `phone`: String
    *   `geometry`: Point (4326)

### `gas_stations`
*   **Source**: `gasstation.csv`
*   **Description**: Gas stations (mostly NGV).
*   **Columns**:
    *   `id`: Integer (PK)
    *   `name`: String
    *   `address`: Text
    *   `district`: String
    *   `brand_type`: String
    *   `geometry`: Point (4326)

### `traffic_points`
*   **Source**: `traffic-manage.csv`
*   **Description**: Traffic management points.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `name`: String
    *   `morning_time`: String
    *   `afternoon_time`: String
    *   `geometry`: Point (4326)

### `water_transport_piers`
*   **Source**: `water-transportation.csv`
*   **Description**: Piers and water transport stops.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `name`: String
    *   `address`: Text
    *   `geometry`: Point (4326)

### `tourist_attractions`
*   **Source**: `china-town-data.csv`
*   **Description**: Tourist attractions (currently focused on China Town).
*   **Columns**:
    *   `id`: Integer (PK)
    *   `name`: String
    *   `description`: Text
    *   `address`: Text
    *   `travel_info`: Text
    *   `open_time`: String
    *   `geometry`: Point (4326)

## Transit (GTFS)

### `transit_stops`
*   **Source**: `bangkok-gtfs/stops.txt`
*   **Description**: Public transit stops.
*   **Columns**:
    *   `stop_id`: String (PK)
    *   `stop_name`: String
    *   `zone_id`: String
    *   `wheelchair_boarding`: String
    *   `geometry`: Point (4326)

### `transit_shapes`
*   **Source**: `bangkok-gtfs/shapes.txt`
*   **Description**: Route shapes aggregated from points.
*   **Columns**:
    *   `shape_id`: String (PK)
    *   `geometry`: LineString (4326)

## Demographics

### `population_grid`
*   **Source**: `bangkok-population.csv`
*   **Description**: Population density grid.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `grid_id`: Integer
    *   `population_density`: Float
    *   `geometry`: Polygon (4326)
