"""
HGT-based Property Price Prediction Service.

Provides inference API for the Heterogeneous Graph Transformer valuator.
Handles cold-start scenarios with context imputation from spatial neighbors.

Features:
- Lazy model loading (singleton pattern)
- Cold-start detection and handling
- Attention-based explainability
- Confidence scores for predictions
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Import torch with fallback
try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not available")

# Model paths
MODELS_DIR = Path("models")
HGT_MODEL_PATH = MODELS_DIR / "hgt_valuator" / "hgt_valuator.pt"
HGT_METADATA_PATH = MODELS_DIR / "hgt_valuator" / "model_metadata.json"
GRAPH_PATH = Path("data") / "hetero_graph.pt"
H3_FEATURES_PATH = Path("data") / "h3_features" / "h3_features_res9.parquet"
HEX2VEC_PATH = MODELS_DIR / "hex2vec" / "hex2vec_embeddings_res9.parquet"

# Default H3 resolution
H3_RESOLUTION = 9


@dataclass
class AttentionExplanation:
    """Attention-based explanation for a prediction."""

    node_type: str  # transit, amenity, flood_zone
    node_name: str  # e.g., "BTS Asoke", "School XYZ"
    attention_weight: float  # 0-1 importance score
    distance_m: float  # Distance to property
    impact_direction: str  # "positive" or "negative"


@dataclass
class HGTPrediction:
    """Complete prediction result from HGT model."""

    property_id: int | None
    predicted_price: float
    confidence: float  # 0-1 prediction confidence
    is_cold_start: bool  # True if property cell has no transaction history

    # Spatial context
    h3_index: str
    district: str | None

    # Explanations
    attention_explanations: list[AttentionExplanation] = field(default_factory=list)

    # Comparison
    h3_cell_avg_price: float | None = None
    district_avg_price: float | None = None
    price_vs_cell: float | None = None  # Percentage difference


class HGTPredictionService:
    """
    Service for HGT-based property price prediction.

    Singleton pattern with lazy loading for efficient resource usage.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._model = None
        self._graph_data = None
        self._h3_features = None
        self._hex2vec_embeddings = None
        self._property_id_to_idx = {}
        self._h3_to_properties = {}
        self._metadata = {}
        self._device = "cpu"
        self._loaded = False
        self._initialized = True

    def _load_model(self):
        """Load HGT model and graph data."""
        if self._loaded:
            return

        if not HAS_TORCH:
            raise ImportError("PyTorch required for HGT prediction")

        # Check if model exists
        if not HGT_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"HGT model not found at {HGT_MODEL_PATH}. "
                "Run the training pipeline first:\n"
                "1. python -m scripts.build_h3_features\n"
                "2. python -m scripts.train_hex2vec\n"
                "3. python -m scripts.build_hetero_graph\n"
                "4. python -m scripts.train_hgt"
            )

        logger.info("Loading HGT model...")

        # Load graph data
        if GRAPH_PATH.exists():
            self._graph_data = torch.load(GRAPH_PATH, map_location=self._device)

            # Build property ID to index mapping
            if hasattr(self._graph_data, "property_ids"):
                self._property_id_to_idx = {
                    pid: idx for idx, pid in enumerate(self._graph_data.property_ids)
                }

        # Load H3 features for context lookup
        if H3_FEATURES_PATH.exists():
            self._h3_features = pd.read_parquet(H3_FEATURES_PATH)

            # Build H3 -> property mapping
            # (would need to track during graph construction)

        # Load Hex2Vec embeddings
        if HEX2VEC_PATH.exists():
            self._hex2vec_embeddings = pd.read_parquet(HEX2VEC_PATH)

        # Load model
        from src.models.hgt_valuator import (
            create_model_from_data,
        )

        self._model = create_model_from_data(self._graph_data)
        self._model.load_state_dict(
            torch.load(HGT_MODEL_PATH, map_location=self._device)
        )
        self._model.eval()

        # Load metadata
        if HGT_METADATA_PATH.exists():
            with open(HGT_METADATA_PATH) as f:
                self._metadata = json.load(f)

        self._loaded = True
        logger.info("HGT model loaded successfully")

    def predict(
        self,
        db: Session,
        lat: float,
        lon: float,
        building_area: float | None = None,
        land_area: float | None = None,
        building_age: float | None = None,
        no_of_floor: float | None = None,
        building_style: str | None = None,
        property_id: int | None = None,
    ) -> HGTPrediction:
        """
        Predict property price using HGT model.

        Args:
            db: Database session for context lookup
            lat, lon: Property coordinates
            building_area, land_area, etc.: Optional property attributes
            property_id: If provided, use cached graph features

        Returns:
            HGTPrediction with price, confidence, and explanations

        """
        self._load_model()

        # Get H3 cell for location
        h3_index = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)

        # Check if this is a cold-start cell
        is_cold_start = self._is_cold_start_cell(h3_index)

        # Check if property exists in graph
        if property_id and property_id in self._property_id_to_idx:
            # Use existing graph node
            prediction, confidence = self._predict_from_graph(property_id)
        else:
            # New property: construct features and predict
            prediction, confidence = self._predict_new_property(
                db,
                lat,
                lon,
                h3_index,
                building_area,
                land_area,
                building_age,
                no_of_floor,
                building_style,
            )

        # Get attention explanations
        attention_explanations = self._get_attention_explanations(
            lat, lon, h3_index, db
        )

        # Get comparison metrics
        h3_cell_avg, district_avg, district = self._get_comparison_metrics(
            db, h3_index, lat, lon
        )

        price_vs_cell = None
        if h3_cell_avg and h3_cell_avg > 0:
            price_vs_cell = ((prediction - h3_cell_avg) / h3_cell_avg) * 100

        return HGTPrediction(
            property_id=property_id,
            predicted_price=prediction,
            confidence=confidence,
            is_cold_start=is_cold_start,
            h3_index=h3_index,
            district=district,
            attention_explanations=attention_explanations,
            h3_cell_avg_price=h3_cell_avg,
            district_avg_price=district_avg,
            price_vs_cell=price_vs_cell,
        )

    def _is_cold_start_cell(self, h3_index: str) -> bool:
        """Check if H3 cell has transaction history."""
        if self._h3_features is None:
            return True

        cell_data = self._h3_features[self._h3_features["h3_index"] == h3_index]
        if cell_data.empty:
            return True

        return cell_data.iloc[0].get("is_cold_start", True)

    def _predict_from_graph(self, property_id: int) -> tuple[float, float]:
        """Predict using existing graph node."""
        idx = self._property_id_to_idx[property_id]

        with torch.no_grad():
            x_dict = {
                k: self._graph_data[k].x
                for k in self._graph_data.node_types
                if hasattr(self._graph_data[k], "x")
            }
            edge_index_dict = {
                k: self._graph_data[k].edge_index
                for k in self._graph_data.edge_types
                if hasattr(self._graph_data[k], "edge_index")
            }

            cold_start_mask = (
                self._graph_data["property"].cold_start_mask
                if hasattr(self._graph_data["property"], "cold_start_mask")
                else None
            )

            predictions, confidence = self._model(
                x_dict,
                edge_index_dict,
                cold_start_mask=cold_start_mask,
                return_confidence=True,
            )

            return predictions[idx].item(), confidence[idx].item()

    def _predict_new_property(
        self,
        db: Session,
        lat: float,
        lon: float,
        h3_index: str,
        building_area: float | None,
        land_area: float | None,
        building_age: float | None,
        no_of_floor: float | None,
        building_style: str | None,
    ) -> tuple[float, float]:
        """
        Predict for a new property not in the graph.

        Strategy:
        1. Get H3 cell context features (POI counts, transit, etc.)
        2. Get Hex2Vec embedding for location
        3. Construct feature vector matching graph node format
        4. Run through model with cold-start handling
        """
        # Get cell context
        cell_features = self._get_cell_features(h3_index)

        # Get Hex2Vec embedding
        hex_embedding = self._get_hex2vec_embedding(h3_index)

        # Encode building style
        style_map = {
            "บ้านเดี่ยว": 0,
            "ทาวน์เฮ้าส์": 1,
            "บ้านแฝด": 2,
            "อาคารพาณิชย์": 3,
            "ตึกแถว": 4,
        }
        style_encoded = style_map.get(building_style, 0) if building_style else 0

        # Construct intrinsic features
        intrinsic = np.array(
            [
                building_area or 0,
                land_area or 0,
                building_age or 0,
                no_of_floor or 1,
                style_encoded,
            ],
            dtype=np.float32,
        )

        # Combine features
        if cell_features is not None and hex_embedding is not None:
            features = np.concatenate([intrinsic, cell_features, hex_embedding])
        elif cell_features is not None:
            features = np.concatenate([intrinsic, cell_features])
        else:
            features = intrinsic

        # For truly cold-start: use simple baseline from cell average
        if self._is_cold_start_cell(h3_index):
            # Fallback to nearest cells with data
            nearby_avg = self._get_nearby_average_price(h3_index, db)
            if nearby_avg:
                # Adjust by property size relative to average
                size_factor = (building_area or 100) / 100
                prediction = nearby_avg * size_factor
                confidence = 0.5  # Low confidence for cold-start
                return prediction, confidence

        # If we have the full graph, we could add this as a temporary node
        # For now, use a simpler approach based on similar cells
        prediction = self._estimate_from_similar_cells(h3_index, features, db)
        confidence = 0.6  # Medium confidence

        return prediction, confidence

    def _get_cell_features(self, h3_index: str) -> np.ndarray | None:
        """Get aggregated features for H3 cell."""
        if self._h3_features is None:
            return None

        cell_data = self._h3_features[self._h3_features["h3_index"] == h3_index]
        if cell_data.empty:
            # Try parent cell (coarser resolution)
            parent = h3.cell_to_parent(h3_index, H3_RESOLUTION - 1)
            cell_data = self._h3_features[self._h3_features["h3_index"] == parent]
            if cell_data.empty:
                return None

        # Extract POI and transit features
        feature_cols = [
            c
            for c in cell_data.columns
            if c.startswith("poi_") or c.startswith("transit_")
        ]
        return cell_data[feature_cols].values[0].astype(np.float32)

    def _get_hex2vec_embedding(self, h3_index: str) -> np.ndarray | None:
        """Get Hex2Vec embedding for H3 cell."""
        if self._hex2vec_embeddings is None:
            return None

        emb_data = self._hex2vec_embeddings[
            self._hex2vec_embeddings["h3_index"] == h3_index
        ]
        if emb_data.empty:
            return np.zeros(64, dtype=np.float32)  # Default zero embedding

        emb_cols = [c for c in emb_data.columns if c.startswith("emb_")]
        return emb_data[emb_cols].values[0].astype(np.float32)

    def _get_nearby_average_price(self, h3_index: str, db: Session) -> float | None:
        """Get average price from nearby H3 cells for cold-start fallback."""
        # Get k-ring neighbors
        neighbors = list(h3.grid_disk(h3_index, 2))  # 2-ring for broader coverage

        if self._h3_features is None:
            return None

        neighbor_data = self._h3_features[self._h3_features["h3_index"].isin(neighbors)]

        if neighbor_data.empty or "avg_price" not in neighbor_data.columns:
            return None

        valid_prices = neighbor_data["avg_price"].dropna()
        if valid_prices.empty:
            return None

        return valid_prices.mean()

    def _estimate_from_similar_cells(
        self,
        h3_index: str,
        features: np.ndarray,
        db: Session,
    ) -> float:
        """Estimate price based on similar H3 cells."""
        if self._h3_features is None or "avg_price" not in self._h3_features.columns:
            # Ultimate fallback: district average
            return self._get_district_average(db, h3_index)

        # Find cells with similar features
        cells_with_price = self._h3_features.dropna(subset=["avg_price"])
        if cells_with_price.empty:
            return self._get_district_average(db, h3_index)

        # Use average of non-empty cells (simplified)
        return cells_with_price["avg_price"].mean()

    def _get_district_average(self, db: Session, h3_index: str) -> float:
        """Get district average price as ultimate fallback."""
        # Get centroid of H3 cell
        lat, lon = h3.cell_to_latlng(h3_index)

        query = """
        SELECT AVG(total_price) as avg_price
        FROM house_prices
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            5000
        )
        """
        result = db.execute(text(query), {"lat": lat, "lon": lon}).fetchone()

        if result and result.avg_price:
            return float(result.avg_price)

        return 3_000_000.0  # Default fallback

    def _get_attention_explanations(
        self,
        lat: float,
        lon: float,
        h3_index: str,
        db: Session,
    ) -> list[AttentionExplanation]:
        """
        Get attention-based explanations for prediction.

        Identifies which transit stops, amenities, and risk zones
        contributed most to the prediction.
        """
        explanations = []

        # Find nearby transit stops
        transit_query = """
        SELECT 
            stop_name,
            source,
            ST_Distance(
                geometry::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) as distance_m
        FROM transit_stops
        WHERE ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            1500
        )
        ORDER BY distance_m
        LIMIT 3
        """

        transit_results = db.execute(
            text(transit_query), {"lat": lat, "lon": lon}
        ).fetchall()

        for row in transit_results:
            # Closer = higher attention (simplified)
            attention = max(0.1, 1.0 - (row.distance_m / 1500))
            explanations.append(
                AttentionExplanation(
                    node_type="transit",
                    node_name=f"{row.source}: {row.stop_name}",
                    attention_weight=attention,
                    distance_m=row.distance_m,
                    impact_direction="positive",
                )
            )

        # Find nearby key amenities
        amenity_query = """
        SELECT 
            name,
            poi_type,
            ST_Distance(
                geometry::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) as distance_m
        FROM view_all_pois
        WHERE poi_type IN ('school', 'hospital', 'mall', 'park')
          AND ST_DWithin(
            geometry::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            1000
        )
        ORDER BY distance_m
        LIMIT 3
        """

        amenity_results = db.execute(
            text(amenity_query), {"lat": lat, "lon": lon}
        ).fetchall()

        for row in amenity_results:
            attention = max(0.1, 1.0 - (row.distance_m / 1000))
            explanations.append(
                AttentionExplanation(
                    node_type="amenity",
                    node_name=f"{row.poi_type}: {row.name or 'Unknown'}",
                    attention_weight=attention,
                    distance_m=row.distance_m,
                    impact_direction="positive",
                )
            )

        # Check flood risk (from H3 features or district lookup)
        if self._h3_features is not None:
            cell_data = self._h3_features[self._h3_features["h3_index"] == h3_index]
            # TODO: Add flood risk when GISTDA API integrated

        # Sort by attention weight
        explanations.sort(key=lambda x: x.attention_weight, reverse=True)

        return explanations[:5]  # Top 5

    def _get_comparison_metrics(
        self,
        db: Session,
        h3_index: str,
        lat: float,
        lon: float,
    ) -> tuple[float | None, float | None, str | None]:
        """Get cell and district average prices for comparison."""
        h3_cell_avg = None
        district_avg = None
        district = None

        # H3 cell average
        if self._h3_features is not None:
            cell_data = self._h3_features[self._h3_features["h3_index"] == h3_index]
            if not cell_data.empty and "avg_price" in cell_data.columns:
                h3_cell_avg = cell_data.iloc[0].get("avg_price")

        # District average
        district_query = """
        SELECT 
            amphur,
            AVG(total_price) as avg_price
        FROM house_prices
        WHERE amphur = (
            SELECT amphur FROM house_prices
            WHERE geometry IS NOT NULL
            ORDER BY ST_Distance(
                geometry::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
            LIMIT 1
        )
        GROUP BY amphur
        """

        result = db.execute(text(district_query), {"lat": lat, "lon": lon}).fetchone()
        if result:
            district = result.amphur
            district_avg = float(result.avg_price) if result.avg_price else None

        return h3_cell_avg, district_avg, district


# Singleton instance
hgt_prediction_service = HGTPredictionService()


# ============================================================================
# TODO: GISTDA Flood Risk Integration
# ============================================================================
#
# When GISTDA API becomes available, implement the following:
#
# class GISTDAFloodService:
#     """
#     Integration with GISTDA flood data API.
#
#     API Endpoint (example): https://gistdaportal.gistda.or.th/data/rest/services/GFlood/WFS
#
#     Methods to implement:
#     1. get_flood_extent(bbox, date) -> GeoDataFrame of flooded areas
#     2. get_historical_floods(bbox) -> List of flood events
#     3. get_flood_risk_level(lat, lon) -> Risk level 1-5
#     """
#
#     def __init__(self, api_key: str = None):
#         self.api_key = api_key or os.getenv("GISTDA_API_KEY")
#         self.wfs_url = "https://gistdaportal.gistda.or.th/data/rest/services/GFlood/WFS"
#
#     def get_flood_risk_for_h3(self, h3_index: str) -> dict:
#         """
#         Get flood risk metrics for an H3 cell.
#
#         Returns:
#             {
#                 "risk_level": 1-5,
#                 "flood_frequency": float,  # Events per year
#                 "max_depth_cm": float,
#                 "last_flood_date": str,
#             }
#         """
#         # TODO: Implement WFS query
#         # from owslib.wfs import WebFeatureService
#         # wfs = WebFeatureService(self.wfs_url, version='2.0.0')
#         # ...
#         pass
#
# ============================================================================
