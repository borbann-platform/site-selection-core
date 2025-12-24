"""
Train price prediction model - Fast version with batch queries.

Usage:
    uv run python scripts/train_price_model.py

Outputs:
    - models/price_model.joblib - trained GradientBoostingRegressor
    - models/model_metadata.json - feature names, training stats
"""

import json
import logging
import os
import sys

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sqlalchemy import text

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODELS_DIR = "models"
MODEL_PATH = os.path.join(MODELS_DIR, "price_model.joblib")
METADATA_PATH = os.path.join(MODELS_DIR, "model_metadata.json")

# Building style encoding
BUILDING_STYLE_ENCODING = {
    "บ้านเดี่ยว": 1,
    "ทาวน์เฮ้าส์": 2,
    "บ้านแฝด": 3,
    "อาคารพาณิชย์": 4,
    "ตึกแถว": 5,
}

FEATURE_NAMES = [
    "building_area",
    "land_area",
    "building_age",
    "no_of_floor",
    "building_style",
    "transit_stops_1km",
    "bus_stops_500m",
    "schools_2km",
    "pois_500m",
    "district_avg_price_sqm",
]


def fetch_training_data_with_features(
    db, limit: int = 2000
) -> tuple[np.ndarray, np.ndarray]:
    """Fetch properties with all features using batch spatial queries."""
    # Main query with spatial joins
    query = text(
        """
        WITH property_base AS (
            SELECT 
                id,
                building_area,
                COALESCE(land_area, 0) as land_area,
                COALESCE(building_age, 10) as building_age,
                COALESCE(no_of_floor, 1) as no_of_floor,
                building_style_desc,
                amphur,
                total_price,
                geometry
            FROM house_prices
            WHERE total_price > 0
              AND total_price < 100000000
              AND building_area > 0
              AND geometry IS NOT NULL
            ORDER BY RANDOM()
            LIMIT :limit
        ),
        district_avg AS (
            SELECT amphur, AVG(total_price / NULLIF(building_area, 0)) as avg_price_sqm
            FROM house_prices
            WHERE total_price > 0 AND building_area > 0
            GROUP BY amphur
        )
        SELECT 
            p.id,
            p.building_area,
            p.land_area,
            p.building_age,
            p.no_of_floor,
            p.building_style_desc,
            p.total_price,
            -- Transit stops within 1km
            (SELECT COUNT(*) FROM transit_stops t 
             WHERE ST_DWithin(t.geometry::geography, p.geometry::geography, 1000)) as transit_1km,
            -- Bus stops within 500m
            (SELECT COUNT(*) FROM bus_shelters b 
             WHERE ST_DWithin(b.geometry::geography, p.geometry::geography, 500)) as bus_500m,
            -- Schools within 2km
            (SELECT COUNT(*) FROM schools s 
             WHERE ST_DWithin(s.geometry::geography, p.geometry::geography, 2000)) as schools_2km,
            -- POIs within 500m
            (SELECT COUNT(*) FROM view_all_pois v 
             WHERE ST_DWithin(v.geometry::geography, p.geometry::geography, 500)) as pois_500m,
            -- District average
            COALESCE(d.avg_price_sqm, 0) as district_avg_sqm
        FROM property_base p
        LEFT JOIN district_avg d ON p.amphur = d.amphur
    """
    )

    logger.info("Executing feature extraction query (this may take a minute)...")
    result = db.execute(query, {"limit": limit})
    rows = result.fetchall()
    logger.info(f"Fetched {len(rows)} properties with features")

    X_list = []
    y_list = []

    for row in rows:
        style_encoded = BUILDING_STYLE_ENCODING.get(row.building_style_desc, 0)

        features = [
            float(row.building_area),
            float(row.land_area),
            float(row.building_age),
            float(row.no_of_floor),
            float(style_encoded),
            float(row.transit_1km),
            float(row.bus_500m),
            float(row.schools_2km),
            float(row.pois_500m),
            float(row.district_avg_sqm),
        ]
        X_list.append(features)
        y_list.append(row.total_price)

    return np.array(X_list), np.array(y_list)


def train_model(X: np.ndarray, y: np.ndarray) -> tuple[GradientBoostingRegressor, dict]:
    """Train GradientBoostingRegressor and return model with metrics."""
    logger.info(f"Training on {len(X)} samples with {X.shape[1]} features")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        min_samples_split=10,
        random_state=42,
    )

    logger.info("Training model...")
    model.fit(X_train, y_train)

    # Evaluate
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    metrics = {
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "train_mae": float(mean_absolute_error(y_train, y_pred_train)),
        "test_mae": float(mean_absolute_error(y_test, y_pred_test)),
        "train_r2": float(r2_score(y_train, y_pred_train)),
        "test_r2": float(r2_score(y_test, y_pred_test)),
    }

    logger.info(f"Train MAE: {metrics['train_mae']:,.0f} THB")
    logger.info(f"Test MAE: {metrics['test_mae']:,.0f} THB")
    logger.info(f"Train R²: {metrics['train_r2']:.3f}")
    logger.info(f"Test R²: {metrics['test_r2']:.3f}")

    # Feature importances
    for name, importance in zip(FEATURE_NAMES, model.feature_importances_):
        logger.info(f"  {name}: {importance:.3f}")

    return model, metrics


def save_model(model: GradientBoostingRegressor, metrics: dict):
    """Save model and metadata."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Save model
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

    # Save metadata
    metadata = {
        "feature_names": FEATURE_NAMES,
        "metrics": metrics,
        "model_type": "GradientBoostingRegressor",
    }

    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Metadata saved to {METADATA_PATH}")


def main():
    logger.info("Starting price model training (fast mode)...")

    db = SessionLocal()
    try:
        # Fetch and extract features in one query
        X, y = fetch_training_data_with_features(db, limit=2000)

        if len(X) < 100:
            logger.error("Not enough training data. Need at least 100 properties.")
            return

        # Train
        model, metrics = train_model(X, y)

        # Save
        save_model(model, metrics)

        logger.info("Training complete!")

    finally:
        db.close()


if __name__ == "__main__":
    main()
