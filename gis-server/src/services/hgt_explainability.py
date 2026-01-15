"""
S2-HGT Explainability Service for Agent Integration.

Provides Top-K anchor attention analysis for property valuations.
Returns structured JSON that the AI Agent can use to explain predictions.

Usage:
    from src.services.hgt_explainability import S2HGTExplainer

    explainer = S2HGTExplainer("models/s2hgt")
    result = explainer.explain_valuation(property_id="12345")

Example output:
    {
        "property_id": "12345",
        "predicted_price": 5200000,
        "source_type": "treasury",
        "price_gap_analysis": {
            "treasury_estimate": 3500000,
            "listing_estimate": 5200000,
            "gap_percent": 48.6,
            "district_avg_gap": 30.0,
            "interpretation": "Above-average gap suggests rapid gentrification"
        },
        "top_anchors": [
            {"name": "BTS Asok", "category": "transit", "distance_m": 450, "attention": 0.34},
            {"name": "Emporium", "category": "retail", "distance_m": 650, "attention": 0.22},
        ],
        "h3_context": {
            "poi_density": "high",
            "flood_risk": "low",
            "transit_access": "excellent"
        }
    }
"""

import json
import logging
from pathlib import Path

import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from torch_geometric.data import HeteroData

    HAS_PYG = True
except ImportError:
    HAS_PYG = False

from src.models.s2_hgt import SOURCE_LISTING, SOURCE_TRANSACTION, SOURCE_TREASURY


class S2HGTExplainer:
    """
    Explainability service for S2-HGT property valuations.

    Provides:
    - Price predictions with source-type awareness
    - Top-K anchor attention weights
    - Price gap analysis (Treasury vs Listing)
    - H3 context summary
    """

    def __init__(self, model_dir: str | Path, graph_path: str | Path | None = None):
        """
        Initialize explainer.

        Args:
            model_dir: Directory containing s2hgt_model.pt and s2hgt_metadata.json
            graph_path: Path to graph file (optional, for batch inference)

        """
        self.model_dir = Path(model_dir)
        self.model = None
        self.metadata = None
        self.graph = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self._load_metadata()

        if graph_path:
            self._load_graph(Path(graph_path))

    def _load_metadata(self):
        """Load model metadata."""
        metadata_path = self.model_dir / "s2hgt_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                self.metadata = json.load(f)
            logger.info(f"Loaded metadata from {metadata_path}")
        else:
            logger.warning(f"Metadata not found at {metadata_path}")
            self.metadata = {}

    def _load_model(self):
        """Lazy load model."""
        if self.model is not None:
            return

        model_path = self.model_dir / "s2hgt_model.pt"
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found at {model_path}")

        # Need graph to infer model architecture
        if self.graph is None:
            raise RuntimeError("Graph must be loaded before model")

        from src.models.s2_hgt import create_s2hgt_from_data

        self.model = create_s2hgt_from_data(
            self.graph, hidden_dim=self.metadata.get("hidden_dim", 128)
        )
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model = self.model.to(self.device)
        self.model.eval()

        logger.info(f"Loaded model from {model_path}")

    def _load_graph(self, graph_path: Path):
        """Load graph data."""
        if not graph_path.exists():
            raise FileNotFoundError(f"Graph not found at {graph_path}")

        self.graph = torch.load(
            graph_path, map_location=self.device, weights_only=False
        )
        logger.info(f"Loaded graph with {len(self.graph.node_types)} node types")

    def predict_with_attention(self, property_indices: list[int] | None = None) -> dict:
        """
        Run prediction and capture attention weights.

        Args:
            property_indices: Specific property indices to predict (None = all)

        Returns:
            Dict with predictions, attention weights, and source types

        """
        self._load_model()

        with torch.no_grad():
            x_dict = {
                k: self.graph[k].x.to(self.device)
                for k in self.graph.node_types
                if hasattr(self.graph[k], "x")
            }
            edge_index_dict = {
                k: self.graph[k].edge_index.to(self.device)
                for k in self.graph.edge_types
                if hasattr(self.graph[k], "edge_index")
            }
            edge_attr_dict = {
                k: self.graph[k].edge_attr.to(self.device)
                for k in self.graph.edge_types
                if hasattr(self.graph[k], "edge_attr")
            }

            source_type = (
                self.graph["property"].source_type.to(self.device)
                if hasattr(self.graph["property"], "source_type")
                else None
            )

            coords_dict = {}
            if hasattr(self.graph["property"], "coords"):
                coords_dict["property"] = self.graph["property"].coords.to(self.device)
            if "anchor" in self.graph.node_types and hasattr(
                self.graph["anchor"], "coords"
            ):
                coords_dict["anchor"] = self.graph["anchor"].coords.to(self.device)

            # Forward with attention capture
            predictions = self.model(
                x_dict,
                edge_index_dict,
                edge_attr_dict=edge_attr_dict,
                source_type=source_type,
                coords_dict=coords_dict if coords_dict else None,
                return_attention=True,
            )

            # Convert from log space if needed
            predictions_thb = torch.expm1(predictions)

        return {
            "predictions": predictions_thb.cpu(),
            "source_type": source_type.cpu() if source_type is not None else None,
            "attention_weights": self.model.attention_weights,
        }

    def explain_valuation(
        self,
        property_id: str | None = None,
        property_idx: int | None = None,
        top_k: int = 5,
    ) -> dict:
        """
        Generate explainability report for a single property.

        Args:
            property_id: Property ID string (looks up in graph.property_ids)
            property_idx: Direct index (if ID not available)
            top_k: Number of top anchors to return

        Returns:
            Structured explanation dict for Agent consumption

        """
        # Resolve index
        if property_id is not None:
            if not hasattr(self.graph, "property_ids"):
                raise ValueError("Graph does not have property_ids mapping")
            try:
                property_idx = self.graph.property_ids.index(property_id)
            except ValueError:
                raise ValueError(f"Property ID {property_id} not found in graph")
        elif property_idx is None:
            raise ValueError("Either property_id or property_idx required")

        # Run prediction
        result = self.predict_with_attention()
        predictions = result["predictions"]
        source_type = result["source_type"]

        predicted_price = float(predictions[property_idx])
        source = (
            int(source_type[property_idx])
            if source_type is not None
            else SOURCE_TREASURY
        )

        source_name = {
            SOURCE_TREASURY: "treasury",
            SOURCE_LISTING: "listing",
            SOURCE_TRANSACTION: "transaction",
        }.get(source, "unknown")

        # Get top anchors
        top_anchors = self._get_top_anchors(property_idx, top_k)

        # Price gap analysis (if we have both source types)
        price_gap = self._analyze_price_gap(property_idx)

        # H3 context
        h3_context = self._get_h3_context(property_idx)

        return {
            "property_id": property_id or str(property_idx),
            "property_idx": property_idx,
            "predicted_price": round(predicted_price),
            "predicted_price_formatted": f"{predicted_price:,.0f} THB",
            "source_type": source_name,
            "price_gap_analysis": price_gap,
            "top_anchors": top_anchors,
            "h3_context": h3_context,
        }

    def _get_top_anchors(self, property_idx: int, top_k: int) -> list[dict]:
        """Extract top-K anchors by attention weight for a property."""
        if "anchor" not in self.model.attention_weights:
            return []

        edge_index, attn_probs = self.model.attention_weights["anchor"]
        src_nodes = edge_index[0].cpu()
        dst_nodes = edge_index[1].cpu()

        # Filter to this property
        mask = src_nodes == property_idx
        if not mask.any():
            return []

        prop_anchors = dst_nodes[mask]
        prop_weights = attn_probs[mask].mean(dim=-1).cpu()  # Average across heads

        # Get edge attributes (distances)
        if ("property", "access", "anchor") in self.graph.edge_types:
            edge_attr = self.graph["property", "access", "anchor"].edge_attr
            edge_indices = edge_index.cpu()
            # Find matching edges
            distances = []
            for anchor_idx in prop_anchors:
                edge_mask = (edge_indices[0] == property_idx) & (
                    edge_indices[1] == anchor_idx
                )
                if edge_mask.any():
                    dist = float(edge_attr[edge_mask][0])
                else:
                    dist = None
                distances.append(dist)
        else:
            distances = [None] * len(prop_anchors)

        # Top-K
        topk_indices = prop_weights.topk(min(top_k, len(prop_weights))).indices

        anchors = []
        for i in topk_indices:
            anchor_idx = int(prop_anchors[i])
            weight = float(prop_weights[i])
            dist = distances[i]

            # Get anchor name/category from graph if available
            anchor_info = {
                "anchor_idx": anchor_idx,
                "attention_weight": round(weight, 3),
            }

            if dist is not None:
                anchor_info["distance_m"] = round(dist)

            if hasattr(self.graph, "anchor_ids"):
                anchor_info["anchor_id"] = self.graph.anchor_ids[anchor_idx]

            # TODO: Add anchor name/category lookup from anchor_nodes.parquet

            anchors.append(anchor_info)

        return anchors

    def _analyze_price_gap(self, property_idx: int) -> dict:
        """
        Analyze price gap between Treasury and Listing estimates.

        This is the "Agent Feature" - showing the gap between official
        appraisal and market asking price.
        """
        if not hasattr(self.graph["property"], "source_type"):
            return {}

        # Get predictions for both source types
        source_type = self.graph["property"].source_type

        # Current property's actual source
        actual_source = int(source_type[property_idx])

        # To get counterfactual predictions, we'd need to run inference
        # with modified source_type. For now, return observed data.
        # TODO: Implement counterfactual prediction

        return {
            "actual_source": {
                SOURCE_TREASURY: "treasury",
                SOURCE_LISTING: "listing",
            }.get(actual_source, "unknown"),
            "note": "Counterfactual gap analysis requires separate inference runs",
        }

    def _get_h3_context(self, property_idx: int) -> dict:
        """Get H3 cell context for a property."""
        if "h3_cell" not in self.graph.node_types:
            return {}

        # Find H3 cell for this property
        if ("property", "in_cell", "h3_cell") not in self.graph.edge_types:
            return {}

        edge_index = self.graph["property", "in_cell", "h3_cell"].edge_index
        mask = edge_index[0] == property_idx
        if not mask.any():
            return {}

        h3_idx = int(edge_index[1][mask][0])
        h3_features = self.graph["h3_cell"].x[h3_idx]

        return {
            "h3_cell_idx": h3_idx,
            "property_count_in_cell": int(h3_features[0])
            if len(h3_features) > 0
            else None,
        }

    def batch_explain(self, property_indices: list[int], top_k: int = 3) -> list[dict]:
        """
        Generate explanations for multiple properties efficiently.

        Runs inference once and extracts explanations for all properties.
        """
        result = self.predict_with_attention()

        explanations = []
        for idx in property_indices:
            explanation = {
                "property_idx": idx,
                "predicted_price": round(float(result["predictions"][idx])),
                "source_type": int(result["source_type"][idx])
                if result["source_type"] is not None
                else 0,
                "top_anchors": self._get_top_anchors(idx, top_k),
            }
            explanations.append(explanation)

        return explanations


def create_explainer(
    model_dir: str = "models/s2hgt", graph_path: str = "data/s2_hetero_graph.pt"
) -> S2HGTExplainer:
    """Factory function for creating explainer instance."""
    return S2HGTExplainer(model_dir=model_dir, graph_path=graph_path)
