# Mock Data Status

This document tracks which endpoints are currently returning mock data and which are connected to real backend services.

## Real Data Endpoints (Connected to DB/Services)

| Endpoint | Method | Description | Source |
| :--- | :--- | :--- | :--- |
| `/house-prices` | GET | Lists appraised house prices | PostGIS queries on `house_prices` table |
| `/house-prices/stats` | GET | Price statistics by district | PostGIS aggregation on `house_prices` table |
| `/site/analyze` | POST | Analyzes location context (POIs, demographics) | PostGIS queries on `pois` and `demographics` tables |
| `/site/nearby` | POST | Returns nearby POIs as GeoJSON | PostGIS queries on `pois` table |
| `/catchment/isochrone` | POST | Calculates travel time isochrones | OSMnx graph analysis (Bangkok road network) |
| `/catchment/analyze` | POST | Calculates isochrone + population | OSMnx graph + PostGIS query on `demographics` |
| `/analytics/grid` | GET | Returns hexagon grid for heatmap | Queries `suitability_grid` table (populated by `generate_grid.py`) |

## Mock Data Endpoints (Hardcoded/Random)

| Endpoint | Method | Description | Reason for Mocking |
| :--- | :--- | :--- | :--- |
| `/price-prediction` | POST | Price prediction AI | ML model not yet trained |

## Next Steps for Real Data

1.  **Run Data Generation Scripts**:
    *   `python -m scripts.generate_grid` to populate analytics grid.
    *   Load house price data with ETL scripts.
2.  **Train Price Prediction Model**: Build ML model for property price prediction based on location, area, and amenities.
