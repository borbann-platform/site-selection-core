"""
Train Spatial Baseline Model for Property Price Prediction.

Uses LightGBM with heavy spatial feature engineering:
- Intrinsic features (building area, land size, age, floors, type)
- H3-aggregated extrinsic features (POI counts, transit density)
- Distance features (to CBD, BTS/MRT, main roads)
- Hex2Vec spatial embeddings (64-dim learned representations)

Evaluation:
- Spatial cross-validation (GroupKFold by district)
- Metrics: RMSE, MAE, MAPE, R²
- SHAP feature importance analysis

Usage:
    python -m scripts.train_baseline --output models/baseline
    python -m scripts.train_baseline --cv-folds 5 --use-hex2vec
"""

import argparse
import json
import logging
from pathlib import Path

import h3
import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sqlalchemy import text
from src.config.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
H3_FEATURES_PATH = DATA_DIR / "h3_features" / "h3_features_res9.parquet"
HEX2VEC_PATH = (
    DATA_DIR.parent / "models" / "hex2vec" / "hex2vec_embeddings_res9.parquet"
)
FLOOD_RISK_PATH = DATA_DIR / "h3_features" / "flood_risk_by_district.parquet"
GTFS_STOPS_PATH = DATA_DIR / "bangkok-gtfs" / "stops.txt"
GTFS_ROUTES_PATH = DATA_DIR / "bangkok-gtfs" / "routes.txt"

# CBD coordinates (lat, lon)
CBD_LOCATIONS = {
    "siam_paragon": (13.7466, 100.5348),  # Retail center
    "asoke": (13.7371, 100.5603),  # Business center
    "silom": (13.7286, 100.5343),  # Financial center
}

# H3 Resolution for spatial indexing
H3_RESOLUTION = 9

# Model hyperparameters
DEFAULT_PARAMS = {
    "n_estimators": 1000,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": -1,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}


def fetch_house_prices() -> pd.DataFrame:
    """Fetch house price data from PostGIS."""
    query = """
    SELECT 
        id,
        building_area,
        land_area,
        building_age,
        no_of_floor,
        building_style_desc,
        amphur as district,
        total_price,
        ST_X(geometry::geometry) as lon,
        ST_Y(geometry::geometry) as lat
    FROM house_prices
    WHERE geometry IS NOT NULL
      AND total_price > 0
      AND building_area > 0
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    logger.info(f"Fetched {len(df)} properties from database")
    return df


def load_transit_stops() -> pd.DataFrame:
    """Load GTFS transit stops, filtering for rail (BTS/MRT/ARL)."""
    stops = pd.read_csv(GTFS_STOPS_PATH)
    routes = pd.read_csv(GTFS_ROUTES_PATH)

    # route_type: 0=tram/light rail, 1=metro, 2=rail
    # Keep only rail-based transit (BTS=0, MRT=1, ARL=2)
    rail_routes = routes[routes["route_type"].isin([0, 1, 2])]
    logger.info(f"Found {len(rail_routes)} rail routes")

    # For simplicity, filter stops by name pattern (BTS/MRT/ARL prefix)
    rail_stops = stops[
        stops["stop_name"].str.contains("BTS|MRT|ARL", case=False, na=False)
    ].copy()
    logger.info(f"Filtered {len(rail_stops)} rail stops")

    return rail_stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]]


def load_h3_features() -> pd.DataFrame:
    """Load pre-computed H3 hexagon features."""
    df = pd.read_parquet(H3_FEATURES_PATH)
    logger.info(f"Loaded H3 features: {df.shape}")
    return df


def load_hex2vec_embeddings() -> pd.DataFrame:
    """Load pre-trained Hex2Vec spatial embeddings."""
    if not HEX2VEC_PATH.exists():
        logger.warning(f"Hex2Vec embeddings not found at {HEX2VEC_PATH}")
        return None
    df = pd.read_parquet(HEX2VEC_PATH)
    logger.info(f"Loaded Hex2Vec embeddings: {df.shape}")
    return df


def load_flood_risk() -> pd.DataFrame:
    """Load flood risk by district."""
    if not FLOOD_RISK_PATH.exists():
        logger.warning(f"Flood risk data not found at {FLOOD_RISK_PATH}")
        return None
    df = pd.read_parquet(FLOOD_RISK_PATH)
    logger.info(f"Loaded flood risk for {len(df)} districts")
    return df


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance in kilometers."""
    R = 6371  # Earth's radius in km

    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    )
    c = 2 * np.arcsin(np.sqrt(a))

    return R * c


def add_distance_features(
    df: pd.DataFrame, transit_stops: pd.DataFrame
) -> pd.DataFrame:
    """Add distance-based features to property dataframe."""
    df = df.copy()

    # Distance to CBD locations
    for name, (cbd_lat, cbd_lon) in CBD_LOCATIONS.items():
        df[f"dist_to_{name}"] = df.apply(
            lambda row: haversine_distance(row["lat"], row["lon"], cbd_lat, cbd_lon),
            axis=1,
        )

    # Minimum distance to any CBD
    cbd_cols = [f"dist_to_{name}" for name in CBD_LOCATIONS]
    df["dist_to_cbd_min"] = df[cbd_cols].min(axis=1)

    # Distance to nearest rail station using KD-Tree for efficiency
    if len(transit_stops) > 0:
        transit_coords = transit_stops[["stop_lat", "stop_lon"]].values
        tree = cKDTree(transit_coords)

        property_coords = df[["lat", "lon"]].values
        # Query returns (distance, index) - distance is in degrees, convert to km
        distances, _ = tree.query(property_coords, k=1)
        # Approximate conversion: 1 degree ≈ 111 km at equator
        df["dist_to_bts"] = distances * 111.0
    else:
        df["dist_to_bts"] = np.nan

    logger.info("Added distance features")
    return df


def add_h3_index(df: pd.DataFrame, resolution: int = H3_RESOLUTION) -> pd.DataFrame:
    """Add H3 hexagonal index to properties."""
    df = df.copy()
    df["h3_index"] = df.apply(
        lambda row: h3.latlng_to_cell(row["lat"], row["lon"], resolution), axis=1
    )
    logger.info(f"Added H3 index (res={resolution})")
    return df


def prepare_features(
    df: pd.DataFrame,
    h3_features: pd.DataFrame,
    hex2vec: pd.DataFrame | None,
    flood_risk: pd.DataFrame | None,
    transit_stops: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prepare full feature matrix by joining all data sources.

    Returns DataFrame with all features ready for modeling.
    """
    # Add H3 index
    df = add_h3_index(df)

    # Add distance features
    df = add_distance_features(df, transit_stops)

    # Join H3 aggregated features
    h3_feature_cols = [
        "h3_index",
        "poi_school",
        "poi_transit_stop",
        "poi_hospital",
        "poi_mall",
        "poi_restaurant",
        "poi_cafe",
        "poi_supermarket",
        "poi_park",
        "poi_temple",
        "poi_total",
        "transit_total",
        "property_count",
    ]
    h3_subset = h3_features[
        [c for c in h3_feature_cols if c in h3_features.columns]
    ].copy()
    df = df.merge(h3_subset, on="h3_index", how="left")
    logger.info(f"Joined H3 features, shape: {df.shape}")

    # Join Hex2Vec embeddings
    if hex2vec is not None:
        df = df.merge(hex2vec, on="h3_index", how="left")
        logger.info(f"Joined Hex2Vec embeddings, shape: {df.shape}")

    # Join flood risk by district
    if flood_risk is not None:
        # Normalize district names for matching
        df["district_clean"] = df["district"].str.strip()
        flood_risk["district_clean"] = (
            flood_risk["district"].str.replace("เขต", "").str.strip()
        )
        df = df.merge(
            flood_risk[["district_clean", "risk_group"]],
            on="district_clean",
            how="left",
        )
        df["flood_risk"] = df["risk_group"].fillna(0).astype(int)
        df = df.drop(columns=["district_clean", "risk_group"], errors="ignore")
        logger.info("Joined flood risk data")

    # Encode categorical: building_style_desc
    le = LabelEncoder()
    df["building_style_encoded"] = le.fit_transform(
        df["building_style_desc"].fillna("unknown")
    )

    # Log-transform target
    df["log_price"] = np.log1p(df["total_price"])

    return df


def get_feature_columns(df: pd.DataFrame, use_hex2vec: bool = True) -> list:
    """Get list of feature columns for modeling."""
    # Intrinsic features
    intrinsic = [
        "building_area",
        "land_area",
        "building_age",
        "no_of_floor",
        "building_style_encoded",
    ]

    # Distance features
    distance = [
        "dist_to_cbd_min",
        "dist_to_bts",
        "dist_to_siam_paragon",
        "dist_to_asoke",
        "dist_to_silom",
    ]

    # H3 aggregated features
    h3_agg = [
        "poi_school",
        "poi_transit_stop",
        "poi_hospital",
        "poi_mall",
        "poi_restaurant",
        "poi_cafe",
        "poi_supermarket",
        "poi_park",
        "poi_temple",
        "poi_total",
        "transit_total",
        "property_count",
    ]

    # Optional: flood risk
    if "flood_risk" in df.columns:
        h3_agg.append("flood_risk")

    # Hex2Vec embeddings
    hex2vec_cols = []
    if use_hex2vec:
        hex2vec_cols = [c for c in df.columns if c.startswith("emb_")]

    all_features = intrinsic + distance + h3_agg + hex2vec_cols

    # Filter to columns that exist
    available = [c for c in all_features if c in df.columns]
    logger.info(f"Using {len(available)} features: {available[:10]}...")

    return available


def compute_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, is_log: bool = True
) -> dict:
    """Compute regression metrics."""
    if is_log:
        # Convert back from log scale for interpretable metrics
        y_true_orig = np.expm1(y_true)
        y_pred_orig = np.expm1(y_pred)
    else:
        y_true_orig = y_true
        y_pred_orig = y_pred

    # Avoid division by zero
    y_true_safe = np.maximum(y_true_orig, 1.0)

    # MAPE
    mape = np.mean(np.abs((y_true_orig - y_pred_orig) / y_true_safe)) * 100

    # MAE
    mae = np.mean(np.abs(y_true_orig - y_pred_orig))

    # RMSE
    rmse = np.sqrt(np.mean((y_true_orig - y_pred_orig) ** 2))

    # R² (on log scale for model comparison)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {"mape": mape, "mae": mae, "rmse": rmse, "r2": r2}


def train_spatial_cv(
    df: pd.DataFrame,
    feature_cols: list,
    target_col: str = "log_price",
    n_folds: int = 5,
    params: dict | None = None,
) -> tuple:
    """
    Train with spatial cross-validation (GroupKFold by district).

    Tests generalization to unseen neighborhoods.
    """
    if params is None:
        params = DEFAULT_PARAMS.copy()

    X = df[feature_cols].fillna(0).values
    y = df[target_col].values
    groups = df["district"].values

    gkf = GroupKFold(n_splits=n_folds)

    fold_metrics = []
    models = []
    oof_predictions = np.zeros(len(df))

    for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        # Districts in this fold
        train_districts = df.iloc[train_idx]["district"].nunique()
        val_districts = df.iloc[val_idx]["district"].unique()

        logger.info(
            f"Fold {fold + 1}/{n_folds}: "
            f"Train={len(train_idx)} ({train_districts} districts), "
            f"Val={len(val_idx)} ({len(val_districts)} districts: {list(val_districts)[:3]}...)"
        )

        # Train LightGBM
        model = lgb.LGBMRegressor(**params)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )

        # Predict
        y_pred = model.predict(X_val)
        oof_predictions[val_idx] = y_pred

        # Compute metrics
        metrics = compute_metrics(y_val, y_pred, is_log=True)
        fold_metrics.append(metrics)
        models.append(model)

        logger.info(
            f"  Fold {fold + 1} Results: "
            f"MAPE={metrics['mape']:.2f}%, MAE={metrics['mae']:,.0f} THB, R²={metrics['r2']:.4f}"
        )

    # Aggregate metrics
    avg_metrics = {
        key: np.mean([m[key] for m in fold_metrics]) for key in fold_metrics[0]
    }
    std_metrics = {
        key: np.std([m[key] for m in fold_metrics]) for key in fold_metrics[0]
    }

    logger.info("\n=== Cross-Validation Results ===")
    logger.info(f"MAPE: {avg_metrics['mape']:.2f}% ± {std_metrics['mape']:.2f}%")
    logger.info(f"MAE:  {avg_metrics['mae']:,.0f} ± {std_metrics['mae']:,.0f} THB")
    logger.info(f"RMSE: {avg_metrics['rmse']:,.0f} ± {std_metrics['rmse']:,.0f} THB")
    logger.info(f"R²:   {avg_metrics['r2']:.4f} ± {std_metrics['r2']:.4f}")

    return (
        models,
        oof_predictions,
        {"avg": avg_metrics, "std": std_metrics, "folds": fold_metrics},
    )


def train_holdout(
    df: pd.DataFrame,
    feature_cols: list,
    target_col: str = "log_price",
    test_size: float = 0.2,
    params: dict | None = None,
) -> tuple:
    """Train with simple holdout split (for final model)."""
    if params is None:
        params = DEFAULT_PARAMS.copy()

    X = df[feature_cols].fillna(0).values
    y = df[target_col].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    logger.info(f"Holdout split: Train={len(X_train)}, Test={len(X_test)}")

    model = lgb.LGBMRegressor(**params)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )

    y_pred = model.predict(X_test)
    metrics = compute_metrics(y_test, y_pred, is_log=True)

    logger.info("\n=== Holdout Test Results ===")
    logger.info(f"MAPE: {metrics['mape']:.2f}%")
    logger.info(f"MAE:  {metrics['mae']:,.0f} THB")
    logger.info(f"RMSE: {metrics['rmse']:,.0f} THB")
    logger.info(f"R²:   {metrics['r2']:.4f}")

    return model, metrics


def train_linear_cv(
    df: pd.DataFrame,
    feature_cols: list,
    target_col: str = "log_price",
    n_folds: int = 5,
) -> tuple:
    """
    Train Ridge Regression with spatial cross-validation.

    Ridge (L2 regularization) chosen over vanilla LinearRegression
    for stability with correlated spatial features.
    """
    X = df[feature_cols].fillna(0).values
    y = df[target_col].values
    groups = df["district"].values

    # Standardize features for linear model
    scaler = StandardScaler()

    gkf = GroupKFold(n_splits=n_folds)
    fold_metrics = []
    oof_predictions = np.zeros(len(df))

    for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        # Fit scaler on train, transform both
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)

        val_districts = df.iloc[val_idx]["district"].unique()
        logger.info(
            f"LinearReg Fold {fold + 1}/{n_folds}: Val={len(val_idx)} ({len(val_districts)} districts)"
        )

        # Ridge regression with alpha=1.0
        model = Ridge(alpha=1.0, random_state=42)
        model.fit(X_train_scaled, y_train)

        y_pred = model.predict(X_val_scaled)
        oof_predictions[val_idx] = y_pred

        metrics = compute_metrics(y_val, y_pred, is_log=True)
        fold_metrics.append(metrics)

        logger.info(
            f"  Fold {fold + 1} Results: "
            f"MAPE={metrics['mape']:.2f}%, MAE={metrics['mae']:,.0f} THB, R²={metrics['r2']:.4f}"
        )

    avg_metrics = {
        key: np.mean([m[key] for m in fold_metrics]) for key in fold_metrics[0]
    }
    std_metrics = {
        key: np.std([m[key] for m in fold_metrics]) for key in fold_metrics[0]
    }

    logger.info("\n=== Linear Regression CV Results ===")
    logger.info(f"MAPE: {avg_metrics['mape']:.2f}% ± {std_metrics['mape']:.2f}%")
    logger.info(f"MAE:  {avg_metrics['mae']:,.0f} ± {std_metrics['mae']:,.0f} THB")
    logger.info(f"R²:   {avg_metrics['r2']:.4f} ± {std_metrics['r2']:.4f}")

    return oof_predictions, {
        "avg": avg_metrics,
        "std": std_metrics,
        "folds": fold_metrics,
    }


def train_rf_cv(
    df: pd.DataFrame,
    feature_cols: list,
    target_col: str = "log_price",
    n_folds: int = 5,
) -> tuple:
    """
    Train Random Forest with spatial cross-validation.

    RF serves as a strong tree-based baseline without boosting.
    """
    X = df[feature_cols].fillna(0).values
    y = df[target_col].values
    groups = df["district"].values

    gkf = GroupKFold(n_splits=n_folds)
    fold_metrics = []
    oof_predictions = np.zeros(len(df))
    models = []

    for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups)):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        val_districts = df.iloc[val_idx]["district"].unique()
        logger.info(
            f"RandomForest Fold {fold + 1}/{n_folds}: Val={len(val_idx)} ({len(val_districts)} districts)"
        )

        model = RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features="sqrt",
            n_jobs=-1,
            random_state=42,
        )
        model.fit(X_train, y_train)

        y_pred = model.predict(X_val)
        oof_predictions[val_idx] = y_pred

        metrics = compute_metrics(y_val, y_pred, is_log=True)
        fold_metrics.append(metrics)
        models.append(model)

        logger.info(
            f"  Fold {fold + 1} Results: "
            f"MAPE={metrics['mape']:.2f}%, MAE={metrics['mae']:,.0f} THB, R²={metrics['r2']:.4f}"
        )

    avg_metrics = {
        key: np.mean([m[key] for m in fold_metrics]) for key in fold_metrics[0]
    }
    std_metrics = {
        key: np.std([m[key] for m in fold_metrics]) for key in fold_metrics[0]
    }

    logger.info("\n=== Random Forest CV Results ===")
    logger.info(f"MAPE: {avg_metrics['mape']:.2f}% ± {std_metrics['mape']:.2f}%")
    logger.info(f"MAE:  {avg_metrics['mae']:,.0f} ± {std_metrics['mae']:,.0f} THB")
    logger.info(f"R²:   {avg_metrics['r2']:.4f} ± {std_metrics['r2']:.4f}")

    return (
        models,
        oof_predictions,
        {"avg": avg_metrics, "std": std_metrics, "folds": fold_metrics},
    )


def analyze_shap(
    model: lgb.LGBMRegressor, X: np.ndarray, feature_names: list, output_dir: Path
) -> None:
    """Run SHAP analysis and save plots."""
    logger.info("Running SHAP analysis...")

    # Sample for efficiency
    sample_size = min(1000, len(X))
    sample_idx = np.random.choice(len(X), sample_size, replace=False)
    X_sample = X[sample_idx]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)

    # Feature importance (mean absolute SHAP)
    importance = pd.DataFrame(
        {
            "feature": feature_names,
            "importance": np.abs(shap_values).mean(axis=0),
        }
    ).sort_values("importance", ascending=False)

    logger.info("\n=== Top 10 Feature Importance (SHAP) ===")
    for i, row in importance.head(10).iterrows():
        logger.info(f"  {row['feature']}: {row['importance']:.4f}")

    # Save importance
    importance.to_csv(output_dir / "shap_importance.csv", index=False)

    # Sanity check
    top_features = importance.head(5)["feature"].tolist()
    if "building_area" not in top_features:
        logger.warning("⚠️  building_area not in top 5 - check data quality!")
    if not any(f.startswith("dist_to") for f in top_features[:10]):
        logger.warning(
            "⚠️  No distance features in top 10 - location signal may be weak"
        )


def save_residuals(df: pd.DataFrame, predictions: np.ndarray, output_dir: Path) -> None:
    """Save predictions and residuals for GNN error analysis."""
    df = df.copy()
    df["predicted_log_price"] = predictions
    df["residual"] = df["log_price"] - predictions
    df["abs_residual"] = np.abs(df["residual"])

    # High-error properties (for GNN focus)
    high_error = df.nlargest(100, "abs_residual")[
        [
            "id",
            "district",
            "building_area",
            "total_price",
            "log_price",
            "predicted_log_price",
            "residual",
        ]
    ]

    high_error.to_csv(output_dir / "high_error_properties.csv", index=False)
    df[["id", "h3_index", "log_price", "predicted_log_price", "residual"]].to_parquet(
        output_dir / "predictions.parquet"
    )

    logger.info(f"Saved residuals to {output_dir}")
    logger.info(f"High-error properties saved: {len(high_error)} rows")


def main():
    parser = argparse.ArgumentParser(description="Train spatial baseline model")
    parser.add_argument(
        "--output", type=str, default="models/baseline", help="Output directory"
    )
    parser.add_argument("--cv-folds", type=int, default=5, help="Number of CV folds")
    parser.add_argument(
        "--use-hex2vec", action="store_true", help="Include Hex2Vec embeddings"
    )
    parser.add_argument(
        "--holdout-only", action="store_true", help="Skip CV, only holdout"
    )
    parser.add_argument(
        "--compare-all",
        action="store_true",
        help="Train and compare all baseline models (Linear, RF, LightGBM)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Spatial Baseline Model Training ===")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Use Hex2Vec: {args.use_hex2vec}")

    # Load data
    df = fetch_house_prices()
    h3_features = load_h3_features()
    hex2vec = load_hex2vec_embeddings() if args.use_hex2vec else None
    flood_risk = load_flood_risk()
    transit_stops = load_transit_stops()

    # Prepare features
    df = prepare_features(df, h3_features, hex2vec, flood_risk, transit_stops)
    feature_cols = get_feature_columns(df, use_hex2vec=args.use_hex2vec)

    logger.info(f"\nDataset: {len(df)} properties, {len(feature_cols)} features")
    logger.info(f"Districts: {df['district'].nunique()}")
    logger.info(
        f"Price range: {df['total_price'].min():,.0f} - {df['total_price'].max():,.0f} THB"
    )

    # Compare all models if requested
    if args.compare_all:
        logger.info("\n" + "=" * 50)
        logger.info("COMPARING ALL BASELINE MODELS")
        logger.info("=" * 50)

        all_metrics = {}

        # 1. Linear Regression (Ridge)
        logger.info("\n--- Training Linear Regression (Ridge) ---")
        _, linear_metrics = train_linear_cv(df, feature_cols, n_folds=args.cv_folds)
        all_metrics["linear"] = linear_metrics

        # 2. Random Forest
        logger.info("\n--- Training Random Forest ---")
        rf_models, _, rf_metrics = train_rf_cv(df, feature_cols, n_folds=args.cv_folds)
        all_metrics["random_forest"] = rf_metrics

        # 3. LightGBM
        logger.info("\n--- Training LightGBM ---")
        lgb_models, oof_preds, lgb_metrics = train_spatial_cv(
            df, feature_cols, n_folds=args.cv_folds
        )
        all_metrics["lightgbm"] = lgb_metrics

        # Save comparison results
        with open(output_dir / "all_models_comparison.json", "w") as f:
            json.dump(all_metrics, f, indent=2)

        # Print comparison table
        logger.info("\n" + "=" * 60)
        logger.info("MODEL COMPARISON SUMMARY (Spatial CV)")
        logger.info("=" * 60)
        logger.info(f"{'Model':<20} {'R²':>10} {'MAPE':>10} {'MAE':>12}")
        logger.info("-" * 60)
        for model_name, metrics in all_metrics.items():
            avg = metrics["avg"]
            std = metrics["std"]
            logger.info(
                f"{model_name:<20} "
                f"{avg['r2']:.4f}±{std['r2']:.3f} "
                f"{avg['mape']:.1f}%±{std['mape']:.1f}% "
                f"{avg['mae']:>10,.0f}"
            )
        logger.info("-" * 60)

        # Use LightGBM as best model for SHAP
        best_model = lgb_models[0]
        save_residuals(df, oof_preds, output_dir)

    elif not args.holdout_only:
        models, oof_preds, cv_metrics = train_spatial_cv(
            df, feature_cols, n_folds=args.cv_folds
        )

        # Save CV results
        with open(output_dir / "cv_metrics.json", "w") as f:
            json.dump(cv_metrics, f, indent=2)

        best_model = models[0]
        save_residuals(df, oof_preds, output_dir)
    else:
        best_model, holdout_metrics = train_holdout(df, feature_cols)

        with open(output_dir / "holdout_metrics.json", "w") as f:
            json.dump(holdout_metrics, f, indent=2)

    # SHAP analysis
    X = df[feature_cols].fillna(0).values
    analyze_shap(best_model, X, feature_cols, output_dir)

    # Save model
    best_model.booster_.save_model(str(output_dir / "lgbm_model.txt"))
    logger.info(f"\nModel saved to {output_dir / 'lgbm_model.txt'}")

    # Save feature list
    with open(output_dir / "features.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    logger.info("\n=== Training Complete ===")


if __name__ == "__main__":
    main()
