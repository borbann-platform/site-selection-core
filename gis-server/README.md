# Real Estate Information Platform API

A FastAPI backend for real estate information, price prediction AI, and property analysis using PostGIS.

## Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (Package Manager)
- Docker & Docker Compose (for PostGIS)

## Quick Start

1.  **Start Database**
    ```bash
    docker-compose up -d
    ```

2.  **Install Dependencies**
    ```bash
    uv sync
    ```

3.  **Load Data** (Run once)
    ```bash
    # Load Points of Interest (OSM)
    uv run python scripts/load_data.py
    
    # Load Population Grid
    uv run python scripts/load_demographics.py
    ```

4.  **Run Server**
    ```bash
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

## Documentation

- **API Docs (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Frontend API Guide:** [docs/api.md](docs/api.md)

## Project Structure

- `src/routes/`: API endpoints (House Prices, Analytics, Projects).
- `src/services/`: Business logic (Price Analysis, Isochrones).
- `src/models/`: Pydantic schemas for real estate data.
- `data/`: Property data, GeoJSON, and GraphML storage.
