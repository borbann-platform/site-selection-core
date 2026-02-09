# Borbann - Real Estate Information Platform

AI-powered property valuation platform for Bangkok, Thailand. Provides intelligent site selection and price predictions using machine learning and graph neural networks.

## Features

- **AI Property Valuation** - Get instant property valuations with ML-powered price predictions
- **AI Chat Agent** - Interactive assistant for property search and location analysis
- **Property Price Prediction** - Predict property values using AI models
- **Site Analytics** - Analyze locations with spatial intelligence
- **Interactive Map** - Explore properties and points of interest in Bangkok
- **Location Intelligence** - Transit scores, walkability, flood risk, and more
- **Enterprise Authentication** - Secure multi-tenant authentication with RBAC
- **Organization & Team Management** - Collaborative workspace with role-based permissions
- **Multi-Model Support** - Compare predictions from multiple ML models
  - LightGBM baseline with spatial features
  - Graph Neural Network (HGT) for complex relationships

## Project Structure

```
borbann/
├── gis-server/         # FastAPI backend
│   ├── src/            # Source code
│   ├── scripts/        # Training scripts
│   ├── tests/          # Test suite
│   └── models/         # Trained ML models
└── frontend/           # React frontend
```

## Getting Started

### Quickstart (Full Stack)

```bash
# From repo root
make stack-up
```

This starts PostGIS, the FastAPI backend on `http://localhost:8000`, and the Vite frontend on `http://localhost:3000`.

### Backend (gis-server)

```bash
cd gis-server

# Install dependencies
uv sync

# Set up database (first time only)
# See docs/DATABASE_SETUP.md for detailed instructions
uv run alembic upgrade head
uv run python src/scripts/seed_permissions.py

# Run development server
uv run uvicorn main:app --reload --port 8000

# Run tests
make test
```

**Requirements:**
- Python 3.11+
- PostgreSQL with PostGIS extension
- uv package manager

**Documentation:**
- [Database Setup Guide](docs/DATABASE_SETUP.md) - Database migrations and permissions

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Useful Root Commands

```bash
make db-up        # Start PostGIS only
make stack-up     # Start full stack (db + backend + frontend)
make test         # Run backend + frontend tests
make lint         # Run backend + frontend lint
```

**Requirements:**
- Node.js 18+
- npm or yarn

## API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Machine Learning

### Train Models

```bash
cd gis-server

# Train baseline models (LightGBM, Random Forest, Linear)
make train-baseline-all

# Train graph neural network
make train-hgt

# View experiment tracking
make mlflow-ui
```

### Model Architecture

1. **Baseline Models** - Traditional ML with spatial features
   - H3 hexagonal indexing for location features
   - POI (Points of Interest) aggregation
   - Distance to CBD and transit stations
   - Hex2Vec spatial embeddings

2. **Graph Neural Network (HGT)** - Heterogeneous graph learning
   - Property-POI-Location relationships
   - Attention mechanisms for feature importance
   - Cold-start property support

## Technology Stack

**Backend:**
- FastAPI - Modern Python web framework
- PostgreSQL + PostGIS - Spatial database
- LightGBM - Gradient boosting models
- PyTorch Geometric - Graph neural networks
- MLflow - Experiment tracking
- H3 - Hexagonal hierarchical spatial indexing
- LangGraph - AI agent orchestration

**Frontend:**
- React 19 - UI framework
- Vite - Build tool
- Deck.gl - WebGL-powered map visualization
- TanStack Router - Type-safe routing

## Environment Variables

Create `.env` file in `gis-server/`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SECRET_KEY=your-secret-key-for-jwt-signing
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
GOOGLE_API_KEY=your_gemini_api_key  # For AI chat agent
```

## Testing

```bash
cd gis-server

# Run all tests (23 tests)
make test

# Run with coverage
make test-cov

# Run specific test suites
make test-unit          # Unit tests only
make test-integration   # Integration tests only
```

## Development

```bash
# Format code
make format

# Run linter
make lint

# Clean cache files
make clean
```

## Data Sources

- Property transactions from public records
- OpenStreetMap for POIs and roads
- Bangkok GTFS data for transit information
- Administrative boundaries from government data

## License

This project is for educational purposes.

## Team

Developed by Kasetsart University students for the Borbann platform.
