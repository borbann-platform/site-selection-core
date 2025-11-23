# Mock Data Status

This document tracks which endpoints are currently returning mock data and which are connected to real backend services.

## Real Data Endpoints (Connected to DB/Services)

| Endpoint | Method | Description | Source |
| :--- | :--- | :--- | :--- |
| `/site/analyze` | POST | Analyzes site potential (competitors, magnets, population) | PostGIS queries on `pois` and `demographics` tables |
| `/site/nearby` | POST | Returns nearby POIs as GeoJSON | PostGIS queries on `pois` table |
| `/catchment/isochrone` | POST | Calculates travel time isochrones | OSMnx graph analysis (Bangkok road network) |
| `/catchment/analyze` | POST | Calculates isochrone + population | OSMnx graph + PostGIS query on `demographics` |
| `/analytics/grid` | GET | Returns hexagon grid for heatmap | Queries `suitability_grid` table (populated by `generate_grid.py`) |
| `/site/{site_id}` | GET | Returns detailed site info by ID | Queries `saved_sites` table (populated by `seed_sites.py`) |

## Mock Data Endpoints (Hardcoded/Random)

| Endpoint | Method | Description | Reason for Mocking |
| :--- | :--- | :--- | :--- |
| None | - | All core endpoints are now connected to DB logic. | - |

## Next Steps for Real Data

1.  **Run Data Generation Scripts**:
    *   `python -m scripts.generate_grid` to populate the suitability grid.
    *   `python -m scripts.seed_sites` to populate the saved sites.
2.  **Refine Scoring Logic**: Update `generate_grid.py` to use real POI/Demographic data for the score instead of distance-based mock.
