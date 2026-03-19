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

3.  **Initialize & Load Data** (Run once)
    ```bash
    # Existing database: apply schema migrations without dropping data
    uv run alembic upgrade head

    # Fresh reset only: recreate all tables (drops existing data)
    uv run python -m scripts.init_db
    
    # Load all data (POIs, transit, real estate, demographics)
    uv run python -m scripts.etl.load_all

    # Optional: load normalized scraper outputs (data/scraped/*.jsonl)
    uv run python -m scripts.etl.load_scraped_projects --include-raw

    # Optional: sync scraped image URLs to MinIO object storage
    # first-time dependency: uv add minio
    uv run python -m scripts.etl.sync_images_to_minio
    
    # Create unified views
    uv run python -m scripts.create_views
    
    # Create user properties table (for valuations)
    uv run python -m scripts.create_user_properties_table
    ```
    
    > Full data load takes ~10-15 minutes. See [docs/data_processing.md](docs/data_processing.md) for details.

4.  **Train ML Models** (Optional but recommended)
    ```bash
    # Start MLflow services (Postgres backend + local artifact volume)
    make mlflow-up

    # Train baseline LightGBM model for price prediction
    make train-baseline
    
    # Or train all baseline models (LightGBM, RF, Linear)
    make train-baseline-all

    # Train HGT model
    make train-hgt

    # View experiment tracking UI
    make mlflow-ui
    ```

5.  **Run Server**
    ```bash
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

## Documentation

- **API Docs (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Frontend API Guide:** [docs/api.md](docs/api.md)
- **Data Processing:** [docs/data_processing.md](docs/data_processing.md)
- **Data Catalog:** [data/DATA_CATALOG.md](data/DATA_CATALOG.md)

## Cache Backend (Memory or Redis)

The API supports cache backend selection via environment variables.

- `CACHE_BACKEND=memory` (default) uses in-process LRU/TTL caches.
- `CACHE_BACKEND=redis` uses Redis for shared cache across workers/instances.

Redis-related settings:

```bash
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
REDIS_KEY_PREFIX=site_select_core
REDIS_SOCKET_TIMEOUT_SECONDS=0.2
```

When running via Docker Compose in this repo, Redis is included and backend is preconfigured to use it.

Cache telemetry is exposed at:

- `GET /api/v1/observability/metrics`

Look for metrics prefixed with:

- `cache_backend_operations_total`
- `cache_backend_operation_duration_*`
- `cache_backend_selected`

## Data Sources

The platform integrates multiple data sources:

| Category | Sources | Records |
|----------|---------|---------|
| POIs | Longdomap, OSM Thailand, BMA | ~710K |
| Transit | Bangkok GTFS (BTS/MRT/ARL), BMTA Bus | ~18K stops |
| Real Estate | Bania, Hipflat, Treasury | ~75K listings |
| Demographics | Bangkok Population Grid | ~6.6K cells |

See [docs/data_processing.md](docs/data_processing.md) for detailed loading instructions.

## AI Chat Agent Setup (Optional)

The chat endpoint supports an intelligent RAG agent powered by Google Gemini and pgvector.

### 1. Configure Environment

Add the following to your `.env` file:

```bash
# Required for agent
GOOGLE_API_KEY=your-gemini-api-key

# Optional customization
AGENT_MODEL=gemini-2.0-flash
EMBEDDING_MODEL=models/text-embedding-004
AGENT_MAX_ITERATIONS=5
RAG_RETRIEVAL_TOP_K=5
```

### 2. Initialize Vector Database

After starting the database:

```bash
# Initialize pgvector tables
uv run python -m scripts.init_vector_db
```

### 3. Seed Knowledge Base (Optional)

Load documentation into the vector store for RAG:

```bash
# Seed from docs folder
uv run python -m scripts.seed_knowledge_base

# Clear and reseed
uv run python -m scripts.seed_knowledge_base --clear
```

### 4. Agent Capabilities

The agent can:
- **Analyze sites** for business potential (competitors, magnets)
- **Get location intelligence** (transit, walkability, schools, flood, noise)
- **Predict property prices** using trained ML models (LightGBM/HGT)
- **Search properties** with filters
- **Get market statistics** by district
- **Analyze catchment areas** with isochrones
- **Retrieve knowledge** from the documentation

### 5. Check Status

```bash
curl http://localhost:8000/chat/status
```

## AI Property Valuation

The `/valuation` endpoint provides ML-powered property price predictions.

### Setup

1. Ensure the baseline model is trained:
   ```bash
   make train-baseline
   ```

2. The valuation endpoint will automatically use the best available model:
   - HGT (Graph Neural Network) - if trained
   - Baseline + Hex2Vec - if available
   - Baseline LightGBM - default

### Features

- **Price Prediction**: Estimates property value based on location and features
- **Confidence Scoring**: High/Medium/Low confidence levels
- **Feature Explanations**: Top factors affecting the price
- **Comparable Properties**: Similar properties within 2km
- **Market Insights**: District averages and trends

## MLOps Workflow (Manual + Strict Gate)

1. Train a model with MLflow tracking (`make train-baseline`, `make train-hgt`).
   - Each run logs standard metadata for comparison:
     `model_family`, `model_variant`, `feature_set`, `dataset_version`, `split_seed`,
     `git_sha`, `git_branch`, `train_timestamp_utc`.
2. Get run IDs from MLflow UI at `http://localhost:5001`.
3. Promote only if strict metric gates pass:

```bash
# Baseline gate (cv_mape_mean, cv_r2_mean)
make promote-baseline RUN_ID=<mlflow_run_id>

# HGT gate (test_mape, test_r2, cold_mape)
make promote-hgt RUN_ID=<mlflow_run_id>

# Export leaderboard report across experiments
make mlflow-leaderboard METRIC=test_mape MODE=min
```

Thresholds are configured in `config/mlops_thresholds.json`.

## Project Structure

- `src/routes/`: API endpoints (House Prices, Analytics, Projects, Valuation, Chat, Auth).
- `src/services/`: Business logic (Price Analysis, Isochrones, Agent, Price Prediction).
- `src/models/`: Pydantic schemas for real estate data.
- `src/config/`: Settings and database configuration.
- `data/`: Property data, GeoJSON, and GraphML storage.
- `scripts/`: Data loading and initialization scripts.
- `docs/`: API documentation and guides.
- `models/`: Trained ML models (baseline, hex2vec, hgt).
