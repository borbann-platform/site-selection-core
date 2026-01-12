# HGT Property Valuation Model - Usage Guide

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          HGT PROPERTY VALUATION PIPELINE                        │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Raw Data   │───►│  H3 Index    │───►│   Hex2Vec    │───►│ HeteroGraph  │
│ (CSV, JSON)  │    │ (Resolution) │    │ (Embeddings) │    │  (PyG Data)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                    │
                                                                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   REST API   │◄───│  Inference   │◄───│   HGT Model  │◄───│   GraphMAE   │
│  Endpoint    │    │   Service    │    │  (Fine-tune) │    │ (Pre-train)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

## How It Works

### Stage 1: Spatial Indexing (H3)

**Script:** `scripts/build_h3_features.py`

Uber's H3 hexagonal grid indexes all entities to uniform spatial cells:
- **Resolution 9** (~0.1 km²): Primary level for neighborhood features
- **Resolution 7/11**: Macro (district) and micro (block) context

Each H3 cell aggregates:
- POI counts by category (schools, hospitals, malls, etc.)
- Transit accessibility (BTS/MRT station counts)
- Flood risk indicators

### Stage 2: Location Embedding (Hex2Vec)

**Script:** `scripts/train_hex2vec.py`

Skip-gram learns dense embeddings for each H3 cell:
1. Build "sentences" = H3 cell ID + POI tags within it
2. Spatial neighbors form contextual sequences
3. Word2Vec learns 64-dim vectors encoding neighborhood signature

Properties inherit embeddings from their containing H3 cell.

### Stage 3: Heterogeneous Graph Construction

**Script:** `scripts/build_hetero_graph.py`

Builds PyTorch Geometric `HeteroData` with:

**Node Types:**
| Type | Features | Source |
|------|----------|--------|
| `property` | price, area, rooms, hex2vec embedding | Database + Hex2Vec |
| `transit` | centrality, line type | GTFS + PageRank |
| `amenity` | category encoding, rating | POI data |
| `flood_zone` | risk level, historical floods | flood-warning.csv |

**Edge Types:**
| Edge | Semantics | Distance Threshold |
|------|-----------|-------------------|
| `property → served_by → transit` | Walking accessibility | 1500m |
| `property → near → amenity` | Nearby facilities | 1000m |
| `property → in_zone → flood` | Risk zone membership | Contains |

### Stage 4: Self-Supervised Pre-training (GraphMAE)

**Script:** `scripts/pretrain_graphmae.py`

Masked autoencoder learns spatial structure without labels:
1. Mask 30% of nodes randomly
2. Reconstruct masked features from graph neighbors
3. Encoder learns transferable representations

This helps cold-start handling—cells with no transactions still learn from neighbors.

### Stage 5: HGT Fine-tuning

**Script:** `scripts/train_hgt.py`  
**Model:** `src/models/hgt_valuator.py`

Heterogeneous Graph Transformer applies meta-relation attention:
- Different attention heads for Property→Transit vs Property→Amenity edges
- 3 HGTConv layers with 128 hidden dimensions
- Final MLP predicts price + confidence score

**Cold-Start Strategy:**
- Properties in cells with no prior transactions marked as "cold"
- `cold_start_aggregator` averages embeddings from k-ring neighbors
- Confidence reduced (0.5-0.6 vs 0.8-0.95 for warm nodes)

### Stage 6: Inference

**Service:** `src/services/hgt_prediction.py`  
**Routes:** `src/routes/hgt_prediction.py`

REST API endpoints:
- `GET /api/v1/hgt/status` - Check service readiness
- `POST /api/v1/hgt/predict` - Predict from lat/lng + features
- `GET /api/v1/hgt/{property_id}/predict` - Predict for DB property

---

## Quick Start

### Prerequisites

```bash
# From gis-server directory
cd gis-server

# Install dependencies (PyTorch + torch-geometric)
poetry install

# Or with pip
pip install torch>=2.0.0 torch-geometric>=2.4.0 gensim>=4.3.0
```

### Run Full Pipeline

```bash
# Option 1: Run all stages
python -m scripts.run_hgt_pipeline

# Option 2: Run individually
python -m scripts.build_h3_features    # Stage 1
python -m scripts.train_hex2vec        # Stage 2
python -m scripts.build_hetero_graph   # Stage 3
python -m scripts.pretrain_graphmae    # Stage 4 (optional but recommended)
python -m scripts.train_hgt            # Stage 5
```

### Evaluate Model

```bash
# Full evaluation with plots and report
python -m scripts.evaluate_hgt

# Custom paths
python -m scripts.evaluate_hgt \
    --model models/hgt_valuator \
    --graph data/hetero_graph.pt \
    --output evaluation
```

**Outputs:**
- `evaluation/evaluation_report.md` - Markdown report
- `evaluation/evaluation_results.json` - Raw metrics
- `evaluation/predicted_vs_actual.png` - Scatter plot
- `evaluation/error_distribution.png` - Error histogram
- `evaluation/cold_start_comparison.png` - Cold vs warm analysis

### Start API Server

```bash
# Development
uvicorn main:app --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Test API

```bash
# Check status
curl http://localhost:8000/api/v1/hgt/status

# Predict from coordinates
curl -X POST http://localhost:8000/api/v1/hgt/predict \
  -H "Content-Type: application/json" \
  -d '{"lat": 13.7563, "lng": 100.5018, "area_sqm": 35, "bedrooms": 1}'

# Predict for existing property
curl http://localhost:8000/api/v1/hgt/1234/predict
```

---

## Key Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `H3_RESOLUTION` | 9 | Primary hex size (~0.1 km²) |
| `HEX2VEC_DIM` | 64 | Embedding dimensions |
| `HGT_HIDDEN` | 128 | GNN hidden layer size |
| `HGT_HEADS` | 4 | Attention heads |
| `HGT_LAYERS` | 3 | Message passing layers |
| `MAX_TRANSIT_DIST` | 1500m | Property→Transit edge threshold |
| `MAX_AMENITY_DIST` | 1000m | Property→Amenity edge threshold |
| `LEARNING_RATE` | 1e-3 | Adam optimizer LR |
| `EPOCHS` | 200 | Max training epochs |
| `EARLY_STOP_PATIENCE` | 15 | Early stopping patience |

---

## Expected Metrics

Based on research benchmarks for Bangkok property valuation:

| Model | MAPE Target | Notes |
|-------|-------------|-------|
| Baseline (mean) | ~40-50% | Simple average |
| GradientBoosting | ~15-25% | Previous model |
| **HGT (warm)** | **10-15%** | Nodes with transaction history |
| **HGT (cold)** | **18-25%** | No local transaction history |

Cold-start MAPE of 18-25% is acceptable given zero local data—model relies purely on spatial context.

---

## Troubleshooting

### "Model not found"
Run `python -m scripts.run_hgt_pipeline` to train first.

### CUDA out of memory
Reduce batch size in `train_hgt.py`:
```python
BATCH_SIZE = 64  # Default 128
```
Or use CPU: `--device cpu`

### Graph too large
Use spatial subsampling or mini-batch training via `NeighborLoader`.

### Cold-start performance poor
1. Increase k-ring radius for neighbor aggregation
2. Run more GraphMAE pre-training epochs
3. Add more spatial features (district-level statistics)
