"""
Train Hex2Vec embeddings for H3 cells.

Uses Skip-gram (Word2Vec) to learn dense vector representations of H3 cells
based on their POI/amenity context. Similar to Word2Vec where words appearing
in similar contexts get similar embeddings, cells with similar POI distributions
get similar embeddings.

Usage:
    python -m scripts.train_hex2vec --input data/h3_features --output models/hex2vec
"""

import argparse
import logging
from pathlib import Path

import h3
import numpy as np
import pandas as pd
from gensim.models import Word2Vec

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hex2Vec hyperparameters
EMBEDDING_DIM = 64
WINDOW_SIZE = 3  # Context window for Skip-gram
MIN_COUNT = 1  # Minimum frequency for tokens
EPOCHS = 50
WORKERS = 4

# POI categories to use as "context words"
POI_CATEGORIES = [
    "school",
    "transit_stop",
    "bus_shelter",
    "police_station",
    "museum",
    "gas_station",
    "water_transport",
    "tourist_attraction",
    "restaurant",
    "cafe",
    "hospital",
    "bank",
    "mall",
    "supermarket",
    "park",
    "temple",
    "university",
]


def load_h3_features(input_dir: Path, resolution: int = 9) -> pd.DataFrame:
    """Load H3 features from parquet file."""
    feature_path = input_dir / f"h3_features_res{resolution}.parquet"
    if not feature_path.exists():
        raise FileNotFoundError(f"H3 features not found at {feature_path}")

    df = pd.read_parquet(feature_path)
    logger.info(f"Loaded {len(df)} H3 cells at resolution {resolution}")
    return df


def build_cell_sentences(features_df: pd.DataFrame) -> list:
    """
    Build "sentences" for Word2Vec training.

    Each sentence represents an H3 cell and its context:
    - Target: H3 cell index
    - Context: POI types present in the cell (repeated by count)

    Format: [cell_index, poi_type_1, poi_type_1, poi_type_2, ...]
    """
    sentences = []

    poi_cols = [
        f"poi_{cat}" for cat in POI_CATEGORIES if f"poi_{cat}" in features_df.columns
    ]

    for _, row in features_df.iterrows():
        cell = row["h3_index"]
        sentence = [cell]  # Start with cell as "target word"

        # Add POI types as "context words" (repeat by count, capped)
        for col in poi_cols:
            count = int(row.get(col, 0))
            if count > 0:
                poi_type = col.replace("poi_", "")
                # Cap repetitions to avoid dominance
                repeat = min(count, 5)
                sentence.extend([poi_type] * repeat)

        # Add transit info as context
        transit_cols = [
            c
            for c in features_df.columns
            if c.startswith("transit_") and c != "transit_total"
        ]
        for col in transit_cols:
            count = int(row.get(col, 0))
            if count > 0:
                transit_type = col.replace("transit_", "")
                repeat = min(count, 3)
                sentence.extend([f"transit_{transit_type}"] * repeat)

        # Add price tier as context (if available)
        avg_price = row.get("avg_price")
        if pd.notna(avg_price) and avg_price > 0:
            # Discretize price into tiers
            if avg_price < 2_000_000:
                sentence.append("price_low")
            elif avg_price < 5_000_000:
                sentence.append("price_medium")
            elif avg_price < 10_000_000:
                sentence.append("price_high")
            else:
                sentence.append("price_luxury")

        # Only add if cell has some context
        if len(sentence) > 1:
            sentences.append(sentence)

    logger.info(f"Built {len(sentences)} sentences for Hex2Vec training")
    return sentences


def build_spatial_sentences(features_df: pd.DataFrame, k_ring: int = 1) -> list:
    """
    Build sentences using spatial neighbors.

    Each sentence is a random walk through neighboring H3 cells,
    capturing spatial co-occurrence patterns.
    """
    sentences = []
    h3_set = set(features_df["h3_index"].tolist())

    for _, row in features_df.iterrows():
        cell = row["h3_index"]
        neighbors = list(h3.grid_disk(cell, k_ring))

        # Filter to cells in our dataset
        valid_neighbors = [n for n in neighbors if n in h3_set]

        if valid_neighbors:
            # Create sentence: cell + its valid neighbors
            sentence = [cell] + valid_neighbors
            sentences.append(sentence)

    logger.info(f"Built {len(sentences)} spatial sentences")
    return sentences


def train_hex2vec(
    sentences: list,
    embedding_dim: int = EMBEDDING_DIM,
    window: int = WINDOW_SIZE,
    min_count: int = MIN_COUNT,
    epochs: int = EPOCHS,
    workers: int = WORKERS,
) -> Word2Vec:
    """
    Train Word2Vec model on cell sentences.

    Uses Skip-gram architecture (sg=1) which works better for
    learning cell embeddings from sparse POI context.
    """
    logger.info(
        f"Training Hex2Vec with dim={embedding_dim}, window={window}, epochs={epochs}"
    )

    model = Word2Vec(
        sentences=sentences,
        vector_size=embedding_dim,
        window=window,
        min_count=min_count,
        workers=workers,
        epochs=epochs,
        sg=1,  # Skip-gram
        negative=10,  # Negative sampling
        seed=42,
    )

    logger.info(f"Trained embeddings for {len(model.wv)} tokens")
    return model


def extract_cell_embeddings(model: Word2Vec, h3_cells: list) -> pd.DataFrame:
    """
    Extract embeddings for H3 cells from trained model.

    Cells not in vocabulary get zero vectors (cold-start handled later in GNN).
    """
    embeddings = []

    for cell in h3_cells:
        if cell in model.wv:
            vec = model.wv[cell]
        else:
            # Cold-start: zero vector (will be filled by GNN message passing)
            vec = np.zeros(model.wv.vector_size)
        embeddings.append(
            {"h3_index": cell, **{f"emb_{i}": v for i, v in enumerate(vec)}}
        )

    df = pd.DataFrame(embeddings)
    logger.info(f"Extracted embeddings for {len(df)} cells")

    # Count cold-start cells
    zero_count = sum(1 for cell in h3_cells if cell not in model.wv)
    logger.info(f"Cold-start cells (zero embeddings): {zero_count}")

    return df


def analyze_embeddings(model: Word2Vec):
    """Log basic embedding analysis."""
    # Find similar POI types
    logger.info("\n=== Embedding Analysis ===")

    # Check if key POI types are in vocabulary
    for poi in ["school", "transit_stop", "park", "mall"]:
        if poi in model.wv:
            similar = model.wv.most_similar(poi, topn=5)
            logger.info(f"Most similar to '{poi}': {similar}")

    # Check a few cells
    cells = [k for k in model.wv.key_to_index if k.startswith("8")][:3]
    for cell in cells:
        similar = model.wv.most_similar(cell, topn=3)
        logger.info(f"Similar to cell {cell[:12]}...: {similar[:3]}")


def save_embeddings(
    model: Word2Vec,
    embeddings_df: pd.DataFrame,
    output_dir: Path,
    resolution: int,
):
    """Save trained model and embeddings."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save Word2Vec model
    model_path = output_dir / f"hex2vec_res{resolution}.model"
    model.save(str(model_path))
    logger.info(f"Saved model to {model_path}")

    # Save embeddings as parquet
    emb_path = output_dir / f"hex2vec_embeddings_res{resolution}.parquet"
    embeddings_df.to_parquet(emb_path, index=False)
    logger.info(f"Saved embeddings to {emb_path}")

    # Save vocabulary
    vocab_path = output_dir / f"hex2vec_vocab_res{resolution}.txt"
    with open(vocab_path, "w") as f:
        f.writelines(f"{word}\n" for word in model.wv.key_to_index)
    logger.info(f"Saved vocabulary to {vocab_path}")


def main():
    parser = argparse.ArgumentParser(description="Train Hex2Vec embeddings")
    parser.add_argument(
        "--input",
        type=str,
        default="data/h3_features",
        help="Input directory with H3 features",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/hex2vec",
        help="Output directory for model and embeddings",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=9,
        help="H3 resolution to train on",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=EMBEDDING_DIM,
        help="Embedding dimension",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=EPOCHS,
        help="Training epochs",
    )
    parser.add_argument(
        "--use-spatial",
        action="store_true",
        help="Include spatial neighbor sentences",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    # Load H3 features
    features_df = load_h3_features(input_dir, args.resolution)

    # Build training sentences
    poi_sentences = build_cell_sentences(features_df)

    if args.use_spatial:
        spatial_sentences = build_spatial_sentences(features_df)
        all_sentences = poi_sentences + spatial_sentences
    else:
        all_sentences = poi_sentences

    # Train Hex2Vec
    model = train_hex2vec(
        all_sentences,
        embedding_dim=args.dim,
        epochs=args.epochs,
    )

    # Analyze embeddings
    analyze_embeddings(model)

    # Extract cell embeddings
    h3_cells = features_df["h3_index"].tolist()
    embeddings_df = extract_cell_embeddings(model, h3_cells)

    # Save outputs
    save_embeddings(model, embeddings_df, output_dir, args.resolution)

    logger.info("Done!")


if __name__ == "__main__":
    main()
