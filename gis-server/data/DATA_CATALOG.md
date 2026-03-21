# Data Catalog

Overview of datasets in `/gis-server/data/` for the Site Selection platform.

---

## 🏠 Real Estate Data

| File/Folder | Records | Size | Description |
|-------------|---------|------|-------------|
| `bkk_house_price.parquet` | — | 320K | House price transactions (processed) |
| `bania-scrape/Data/` | ~73K | 127M | Scraped property listings from Bania |
| ├─ `house_all.csv` | 19,687 | 37M | Detached houses |
| ├─ `townhome_all.csv` | 19,615 | 38M | Townhomes |
| ├─ `apartment_all.csv` | 17,140 | 27M | Apartments |
| └─ `office_all.csv` | 16,395 | 25M | Commercial offices |
| `hipflat-scrape/` | 2,388 | 43M | Condo listings from Hipflat (JSON) |

**Bania Fields:** `bathrooms`, `bedrooms`, `price`, `land_size_sqw`, `usable_area_sqm`, `latitude`, `longitude`, `facilities`, `furniture_status`, `property_type`, etc.

---

## 🚇 Transit Data (GTFS)

### `bangkok-gtfs/` — Official Rail Transit
| File | Records | Content |
|------|---------|---------|
| `stops.txt` | 13,722 | BTS/MRT/ARL station locations |
| `routes.txt` | 1,450 | Transit lines (Sukhumvit, Silom, Blue Line, etc.) |
| `stop_times.txt` | 134,194 | Scheduled arrivals/departures |
| `trips.txt` | 3,478 | Trip definitions |
| `shapes.txt` | 330,512 | Route geometry points |
| `fare_*.txt` | 539K+ | Fare rules and attributes |

### `longdomap-bus-gtfs/` — Bus Network (Longdo Map)
| File | Records | Content |
|------|---------|---------|
| `stops.txt` | 4,222 | Bus stop locations |
| `routes.txt` | 457 | BMTA bus routes |
| `stop_times.txt` | 27,980 | Bus schedules |

---

## 🗺️ Geospatial Data

| File | Size | Description |
|------|------|-------------|
| `Bangkok.osm.geojson` | 303M | OpenStreetMap extract for Bangkok (all features) |
| `thailand-260111.osm.pbf` | 300M | OpenStreetMap Thailand extract (POIs for extended coverage) |
| `bangkok_graph.graphml` | 37M | Road network graph (for routing/catchment) |
| `hetero_graph.pt` | 8.6M | PyTorch heterogeneous graph (HGT model input) |

### OSM Thailand POI Integration

The `thailand-260111.osm.pbf` file extends POI coverage beyond Bangkok-only datasets to match the `bkk_house_price.parquet` extent. This addresses spatial bias where existing POI sources (schools, police stations, etc.) only cover central Bangkok.

**Processing:** `python -m scripts.etl.load_osm_pois`

**Coverage:** Filtered to Bangkok + nearby (lat: 13.4-14.2°, lon: 100.2-101.0°)

**Deduplication:** Spatial + name-based matching against existing POI sources to avoid double-counting. Duplicates are flagged (`is_duplicate=TRUE`) but retained for audit. Export duplicates: `--export-duplicates`

**POI Categories Extracted:**
- Education: school, university, library
- Healthcare: hospital, pharmacy
- Services: bank, police_station, post_office
- Commercial: restaurant, cafe, supermarket, mall, convenience_store
- Recreation: park, sports, fitness
- Religious: temple
- Transport: gas_station, transit_stop, water_transport

---

## 📊 H3 Hexagon Features

Aggregated spatial features at multiple H3 resolutions.

| File | Size | Resolution |
|------|------|------------|
| `h3_features_res7.parquet` | 1.4M | ~5km² hexagons |
| `h3_features_res9.parquet` | 5.5M | ~100m² hexagons |
| `h3_features_res11.parquet` | 12M | ~25m² hexagons |
| `h3_features_all.parquet` | 18M | Combined resolutions |
| `flood_risk_by_district.parquet` | 4K | District-level flood risk |

---

## 🏛️ Points of Interest (POIs)

| File | Records | Description |
|------|---------|-------------|
| `longdomap-contributed-pois.csv` | 677,428 | User-contributed POIs (shops, buildings, landmarks) |
| `gasstation.csv` | 393 | PTT gas stations with NGV |
| `school-bma.csv` | 439 | BMA schools (public) |
| `police_station.csv` | 89 | Police stations |
| `local_museum.csv` | 27 | District museums |
| `water-transportation.csv` | 56 | River piers/ferry stops |
| `bus-shelter.csv` | 2,329 | Bus shelters with coordinates |

**POI Fields (longdomap):** `name_th`, `name_en`, `latitude`, `longitude`, `poi_type`, `telephone`, `website`

---

## ⚠️ Risk & Infrastructure

| File | Records | Description |
|------|---------|-------------|
| `flood-warning.csv` | 50 | Flood risk zones by district (2023) |
| `traffic-manage.csv` | 6 | Traffic management points |
| `bangkok-population.csv` | 6,634 | Population density grid (500m cells) |

**Flood Risk Fields:** `risk_id`, `risk_year`, `risk_group`, `District`, `risk_type`, `area`

---

## 🏯 Cultural/Tourism

| File | Records | Description |
|------|---------|-------------|
| `china-town-data.csv` | 61 | Chinatown landmarks & attractions |

**Fields:** `nname`, `activity`, `history`, `travel`, `address`, `latitude`, `longitude`, `oc_time`

---

## 📁 File Format Summary

| Format | Count | Purpose |
|--------|-------|---------|
| `.csv` | 14 | Tabular data (POIs, schools, etc.) |
| `.parquet` | 6 | Columnar storage (prices, H3 features) |
| `.geojson` | 1 | Spatial features (OSM) |
| `.graphml` | 1 | Network graph (routing) |
| `.pt` | 1 | PyTorch model/graph |
| `.txt` (GTFS) | 20 | Transit schedules |
| `.json` | 1 | Scraped condo data |

---

## Usage Notes

1. **Real Estate Models**: Use `bkk_house_price.parquet` for training; `bania-scrape/` and `hipflat-scrape/` for enrichment.
2. **Transit Analysis**: `bangkok-gtfs/` for rail, `longdomap-bus-gtfs/` for buses.
3. **Spatial Indexing**: `h3_features_*.parquet` provides pre-computed features per hexagon.
4. **Graph Neural Networks**: `hetero_graph.pt` is the input for HGT valuator model.
5. **Routing/Catchment**: `bangkok_graph.graphml` for isochrone and accessibility analysis.
