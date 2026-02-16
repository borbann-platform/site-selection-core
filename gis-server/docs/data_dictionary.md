# Data Dictionary

This document describes the database schema for the Real Estate Information Platform.

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

## Real Estate

### `condo_projects`
*   **Source**: `hipflat-scrape/condos_data_bangkok.json`
*   **Description**: Condo projects scraped from Hipflat.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `project_base_url`: String (Unique)
    *   `name`: String
    *   `location`: Text
    *   `completed_date`, `floors`, `units`, `buildings`: String
    *   `price_sale`, `sale_units`, `price_rent`, `rent_units`: String
    *   `description`: Text
    *   `facilities`, `nearby_projects`, `images`, `units_for_sale`, `units_for_rent`, `market_stats`: JSON
    *   `geometry`: Point (4326)

### `real_estate_listings`
*   **Source**: `bania-scrape/Data/*.csv`
*   **Description**: Real estate listings scraped from Bania.
*   **Columns**:
    *   `id`: Integer (PK)
    *   `source_file`: String
    *   `title`: String
    *   `property_type`: String
    *   `price`: String
    *   Various property attributes (bedrooms, bathrooms, area, etc.)
    *   `geometry`: Point (4326)

### `scraped_listings`
*   **Source**: `data/scraped/*.jsonl` (Baania/Hipflat house-project spiders)
*   **Description**: Normalized project-level metadata from scraper JSONL outputs.
*   **Columns**:
    *   `id`: BigInteger (PK)
    *   `source`, `source_listing_id`: Source key (unique together)
    *   `source_url`, `detail_url`, `source_search_url`: URL lineage
    *   `title`, `title_th`, `title_en`, `property_type`, `property_types`
    *   `province*`, `district*`, `subdistrict*`, `status`
    *   `price_start`, `price_end`
    *   `latitude`, `longitude`, `geometry` (Point 4326)
    *   `main_image_url`, `image_count`
    *   `scraped_at`, `raw_payload`, `created_at`, `updated_at`

### `scraped_listing_images`
*   **Source**: Derived from `scraped_listings.image_urls`
*   **Description**: Image URL catalog and object-storage sync metadata.
*   **Columns**:
    *   `id`: BigInteger (PK)
    *   `listing_id`: FK -> `scraped_listings.id`
    *   `source_url`, `source_host`, `image_role`, `image_order`, `is_primary`
    *   `storage_bucket`, `object_key`, `object_uri`
    *   `checksum_sha256`, `mime_type`, `size_bytes`, `width`, `height`
    *   `fetch_status`, `last_http_status`, `fetch_error`, `fetched_at`
    *   `created_at`, `updated_at`

### `house_prices`
*   **Source**: `bkk_house_price.parquet`
*   **Description**: Appraised house prices from Treasury Department (กรมธนารักษ์).
*   **Columns**:
    *   `id`: Integer (PK)
    *   `updated_date`: Date - Appraisal date
    *   `land_type_desc`: String - จัดสรรโครงการเก่า/ใหม่
    *   `building_style_desc`: String - บ้านเดี่ยว, ทาวน์เฮ้าส์, บ้านแฝด, อาคารพาณิชย์, อื่นๆ
    *   `tumbon`: String - Sub-district (แขวง/ตำบล)
    *   `amphur`: String - District (เขต/อำเภอ)
    *   `province`: String - Province (always กรุงเทพมหานคร)
    *   `village`: String - Village/Project name (หมู่บ้าน)
    *   `building_age`: Float - Age in years
    *   `land_area`: Float - Area in square wah (ตร.ว.)
    *   `building_area`: Float - Area in square meters (ตร.ม.)
    *   `no_of_floor`: Float - Number of floors
    *   `total_price`: Float - Appraised price in THB
    *   `geometry`: Point (4326)

## Materialized Views

### `view_all_pois`
*   **Description**: Unified view of all POIs with standardized schema.
*   **Sources**: schools, police_stations, museums, gas_stations, traffic_points, water_transport_piers, tourist_attractions, bus_shelters, transit_stops, contributed_pois
*   **Columns**: id, original_id, name, type, source, geometry

### `view_residential_supply`
*   **Description**: Unified view of all residential supply data.
*   **Sources**: condo_projects, real_estate_listings, house_prices
*   **Columns**: id, original_id, name, type, price, source, geometry
