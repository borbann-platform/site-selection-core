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
    # Create database tables
    uv run python -m scripts.init_db
    
    # Load all data (POIs, transit, real estate, demographics)
    uv run python -m scripts.etl.load_all
    
    # Create unified views
    uv run python -m scripts.create_views
    ```
    
    > ⏱️ Full data load takes ~10-15 minutes. See [docs/data_processing.md](docs/data_processing.md) for details.

4.  **Run Server**
    ```bash
    uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

## Documentation

- **API Docs (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Frontend API Guide:** [docs/api.md](docs/api.md)
- **Data Processing:** [docs/data_processing.md](docs/data_processing.md)
- **Data Catalog:** [data/DATA_CATALOG.md](data/DATA_CATALOG.md)

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
- **Predict property prices** with SHAP explanations
- **Search properties** with filters
- **Get market statistics** by district
- **Analyze catchment areas** with isochrones
- **Retrieve knowledge** from the documentation

### 5. Check Status

```bash
curl http://localhost:8000/chat/status
```

## Project Structure

- `src/routes/`: API endpoints (House Prices, Analytics, Projects).
- `src/services/`: Business logic (Price Analysis, Isochrones, Agent).
- `src/models/`: Pydantic schemas for real estate data.
- `src/config/`: Settings and database configuration.
- `data/`: Property data, GeoJSON, and GraphML storage.
- `scripts/`: Data loading and initialization scripts.
- `docs/`: API documentation and guides.
