# Data Processing & Ingestion Guide

This document provides comprehensive instructions for setting up and seeding the database with all required datasets.

## Quick Start (TL;DR)

```bash
# 1. Start database
docker-compose up -d

# 2. Initialize tables
uv run python -m scripts.init_db

# 3. Load all data (takes ~10-15 minutes)
uv run python -m scripts.etl.load_all

# 4. Create materialized views
uv run python -m scripts.create_views

# 5. (Optional) Build H3 features for ML models
uv run python -m scripts.build_h3_features
```

---

## Prerequisites

1. **Docker & Docker Compose** - For PostGIS database
2. **Python 3.13+** with [uv](https://github.com/astral-sh/uv) package manager
3. **Data files** - See [DATA_CATALOG.md](../data/DATA_CATALOG.md) for required datasets

### Required Data Files

Download and place these files in the `data/` directory:

| File/Folder | Size | Required | Description |
|-------------|------|----------|-------------|
| `bkk_house_price.parquet` | 320KB | ✅ Yes | House price transactions |
| `bania-scrape/Data/` | 127MB | ✅ Yes | Property listings |
| `hipflat-scrape/` | 43MB | ✅ Yes | Condo projects (JSON) |
| `longdomap-contributed-pois.csv` | 50MB+ | ✅ Yes | User-contributed POIs |
| `bangkok-gtfs/` | ~50MB | ✅ Yes | Rail transit GTFS |
| `longdomap-bus-gtfs/` | ~5MB | ✅ Yes | Bus network GTFS |
| `thailand-260111.osm.pbf` | 300MB | ⚠️ Recommended | OSM Thailand (extended POI coverage) |
| `Bangkok.osm.geojson` | 303MB | Optional | OSM Bangkok (legacy) |
| `school-bma.csv` | <1MB | ✅ Yes | BMA schools |
| `police_station.csv` | <1MB | ✅ Yes | Police stations |
| `gasstation.csv` | <1MB | ✅ Yes | Gas stations |
| Other CSVs | <1MB each | Optional | Museums, bus shelters, etc. |

---

## Step-by-Step Setup

### Step 1: Start the Database

```bash
docker-compose up -d
```

This starts a PostGIS container with:
- PostgreSQL 16 + PostGIS 3.4
- pgvector extension (for RAG)
- Port: 5432 (default)

Verify it's running:
```bash
docker-compose ps
```

### Step 2: Configure Environment

Create a `.env` file (or copy from `.env.example`):

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gis_db

# Optional: For AI chat agent
GOOGLE_API_KEY=your-gemini-api-key
```

### Step 3: Initialize Database Schema

```bash
uv run python -m scripts.init_db
```

This creates all tables defined in `src/models/`:
- `house_prices` - Property transactions
- `schools`, `police_stations`, `museums`, etc. - POI tables
- `transit_stops`, `transit_shapes` - GTFS data
- `contributed_pois` - Longdomap POIs
- `osm_pois` - OSM Thailand POIs
- `population_grid` - Demographics
- `condo_projects`, `real_estate_listings` - Scraped listings

### Step 4: Load All Data

```bash
uv run python -m scripts.etl.load_all
```

**Estimated time:** 10-15 minutes

This runs the following loaders in sequence:

| Loader | Data Source | Records |
|--------|-------------|---------|
| `load_places.py` | CSVs (schools, police, etc.) | ~3,400 |
| `load_contributed_pois.py` | longdomap-contributed-pois.csv | ~677,000 |
| `load_osm_pois.py` | thailand-260111.osm.pbf | ~29,000 |
| `load_gtfs.py` | bangkok-gtfs/, longdomap-bus-gtfs/ | ~18,000 |
| `load_population.py` | bangkok-population.csv | ~6,600 |
| `load_realestate.py` | bania-scrape/, hipflat-scrape/ | ~75,000 |
| `load_scraped_projects.py` | scraped/*.jsonl (Baania/Hipflat spiders) | Varies |
| `load_house_prices.py` | bkk_house_price.parquet | Varies |

### Step 5: Create Materialized Views

```bash
uv run python -m scripts.create_views
```

This creates:
- `mat_all_pois` - Unified POI view (all sources combined)
- `view_all_pois` - Alias for `mat_all_pois`
- `view_residential_supply` - Combined listings view
- `view_transit_lines` - Transit routes

### Step 6: Verify Data Load

```bash
uv run python -c "
from sqlalchemy import text
from src.config.database import engine

with engine.connect() as conn:
    result = conn.execute(text('SELECT source, COUNT(*) FROM mat_all_pois GROUP BY source'))
    print('POIs by source:')
    for row in result:
        print(f'  {row[0]}: {row[1]:,}')
"
```

Expected output:
```
POIs by source:
  contributed: 677,427
  osm_thailand: 29,111
  bangkok_gtfs: 13,721
  longdomap_bus: 4,222
  bma: 3,391
```

---

## Individual Data Loaders

### POI Data

**BMA Places (schools, police, museums, etc.):**
```bash
uv run python -m scripts.etl.load_places
```

**Longdomap Contributed POIs:**
```bash
uv run python -m scripts.etl.load_contributed_pois
```

**OSM Thailand POIs (with deduplication):**
```bash
# Full load with dedup
uv run python -m scripts.etl.load_osm_pois

# Export duplicates for review
uv run python -m scripts.etl.load_osm_pois --export-duplicates

# Skip deduplication (faster, but may have duplicates)
uv run python -m scripts.etl.load_osm_pois --skip-dedup
```

### Transit Data (GTFS)

```bash
uv run python -m scripts.etl.load_gtfs
```

Loads from:
- `bangkok-gtfs/` - BTS, MRT, ARL stations
- `longdomap-bus-gtfs/` - BMTA bus stops

### Real Estate Data

```bash
uv run python -m scripts.etl.load_realestate
```

Loads:
- `bania-scrape/Data/*.csv` - Property listings
- `hipflat-scrape/*.json` - Condo projects

**House prices (Treasury data):**
```bash
uv run python -m scripts.etl.load_house_prices
```

**Normalized scraped project pipeline (JSONL):**
```bash
# Load scraped project metadata + image URL catalog into Postgres
uv run python -m scripts.etl.load_scraped_projects --include-raw

# Sync pending/failed image URLs to MinIO object storage
# (requires minio Python client: `uv add minio` once)
uv run python -m scripts.etl.sync_images_to_minio
```

### Demographics

```bash
uv run python -m scripts.etl.load_population
```

Loads `bangkok-population.csv` (500m grid cells with population density).

---

## Building ML Features

### H3 Hexagonal Features

After loading POI data, build H3-indexed features for the ML models:

```bash
# Build features at resolution 9 (default, ~100m² hexagons)
uv run python -m scripts.build_h3_features

# Build at specific resolution
uv run python -m scripts.build_h3_features --resolution 9

# Output to specific file
uv run python -m scripts.build_h3_features --output data/h3_features/h3_res9.parquet
```

### Heterogeneous Graph (for HGT model)

```bash
uv run python -m scripts.build_hetero_graph
```

Outputs: `data/hetero_graph.pt`

---

## OSM POI Deduplication

When loading OSM POIs, the script automatically detects duplicates against existing data sources.

### How Deduplication Works

1. **Tier 1 (Exact match):** Same normalized name within 5m → flagged as duplicate
2. **Tier 2 (Type match):** Same POI type within 30m with similar name → flagged
3. **Chain stores:** Multiple locations allowed (e.g., two 7-Elevens near each other)

### Review Duplicates

```bash
# Export flagged duplicates to CSV
uv run python -m scripts.etl.load_osm_pois --export-duplicates
```

Output: `data/osm_poi_duplicates.csv`

Columns: `id`, `osm_id`, `name`, `poi_type`, `duplicate_of`, `duplicate_reason`, `lat`, `lon`

### Adjust Thresholds

Edit `scripts/etl/load_osm_pois.py`:

```python
EXACT_MATCH_DISTANCE_M = 5      # Distance for exact name match
SPATIAL_TYPE_MATCH_DISTANCE_M = 30  # Distance for type-based match
NAME_SIMILARITY_THRESHOLD = 0.7  # Trigram similarity (if enabled)
```

---

## Refreshing Data

### Refresh Materialized Views

After adding new data, refresh the views:

```bash
uv run python -m scripts.create_views
```

Or manually refresh without recreating:

```sql
REFRESH MATERIALIZED VIEW mat_all_pois;
```

### Re-run Specific Loader

Most loaders have `clear_existing=True` by default, which replaces existing data:

```bash
# Reload OSM POIs
uv run python -m scripts.etl.load_osm_pois

# Reload without clearing (append)
uv run python -m scripts.etl.load_osm_pois --no-clear
```

---

## Troubleshooting

### Database Connection Failed

```bash
# Check if container is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart container
docker-compose restart
```

### Table Already Exists

```bash
# Drop all tables and recreate
uv run python -c "
from src.config.database import engine, Base
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
"
```

### Large File Loading Issues

For files >50MB (e.g., `longdomap-contributed-pois.csv`):
- The loader processes in chunks automatically
- Ensure sufficient memory (4GB+ recommended)

### OSM PBF Extraction Slow

First-time extraction from `thailand-260111.osm.pbf` takes ~3-4 minutes.
- Uses `pyrosm` library
- Bounding box filter applied during extraction

---

## Data Inventory

| File Name | Description | Status | Processing Notes |
|-----------|-------------|--------|------------------|
| `bangkok-population.csv` | Population grid | ✅ Usable | Contains WKT geometry |
| `bus-shelter.csv` | Bus shelters | ✅ Usable | Parse `coordinates` string |
| `china-town-data.csv` | Chinatown POIs | ✅ Usable | Has lat/lon |
| `flood-warning.csv` | Flood risk | ⚠️ Needs geocoding | District names only |
| `gasstation.csv` | Gas stations | ✅ Usable | Has lat/lng |
| `local_museum.csv` | Museums | ✅ Usable | Has lat/lng |
| `police_station.csv` | Police stations | ✅ Usable | Has lat/lng |
| `school-bma.csv` | BMA Schools | ✅ Usable | Has LATITUDE/LONGITUDE |
| `traffic-manage.csv` | Traffic points | ✅ Usable | Has lat/lon |
| `water-transportation.csv` | Ferry piers | ✅ Usable | Has lat/lon |
| `Bangkok.osm.geojson` | OSM Bangkok | ✅ Usable | GeoJSON format |
| `thailand-260111.osm.pbf` | OSM Thailand | ✅ Usable | PBF format, filtered to BKK |
| `bangkok-gtfs/` | Rail GTFS | ✅ Usable | Standard GTFS |
| `longdomap-bus-gtfs/` | Bus GTFS | ✅ Usable | Standard GTFS |
| `bania-scrape/` | Listings (CSV) | ✅ Usable | Has lat/lon |
| `hipflat-scrape/` | Condos (JSON) | ✅ Usable | Has lat/lon |
| `longdomap-contributed-pois.csv` | POIs | ✅ Usable | Large file, chunked loading |
| `bkk_house_price.parquet` | Prices | ✅ Usable | Parquet format |

---

## See Also

- [DATA_CATALOG.md](../data/DATA_CATALOG.md) - Detailed dataset descriptions
- [data_dictionary.md](data_dictionary.md) - Field definitions
- [api.md](api.md) - API documentation
