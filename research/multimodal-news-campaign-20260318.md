# Multimodal + News Campaign Tracker (2026-03-18)

This tracker freezes the current benchmark baseline and starts Phase 1 preparation for image-feature experiments under the current data constraint.

---

## 1. Scope and Constraint

- Constraint: no meaningful increase in clean labeled listing rows right now
- Allowed new signal families:
  - listing images (already collected/uploaded)
  - geolocated news around areas
- Campaign objective: improve listing-side MAE without unacceptable Treasury regression

---

## 2. Phase 0 Baseline Freeze

### Fixed References

- Plan reference: `research/combined-treasury-listing-price-prediction-plan.md`
- Journal reference: `research/price-model-research-journal.md`
- Current-state reference: `research/combined-price-current-state.md`

### Code Snapshot

- Frozen git SHA: `03d6f364678319ebf3bfbc156bad3294d36da827`
- Baseline trainer: `gis-server/scripts/train_combined_price_model_mlflow.py`
- Baseline dataset: `gis-server/data/benchmarks/combined_sales_v1.parquet`
- Grouped split artifact: `gis-server/data/benchmarks/combined_sales_v1_grouped_cv_splits.parquet`
- Time split artifact: `gis-server/data/benchmarks/combined_sales_v1_time_split.parquet`

### Official Baseline Numbers For This Campaign

1) Clean grouped C5 (strong clean benchmark reference)
- MLflow run: `c3677261fc0448c59624d74021b4716d`
- Overall MAE: `1,004,694`
- Treasury MAE: `800,960`
- Listing MAE: `4,385,973`

2) Two-stage grouped C5 leader (current best mixed benchmark tradeoff)
- MLflow run: `4878bc4faa49431a83d47932460483c4`
- Overall MAE: `996,616`
- Treasury MAE: `814,572`
- Listing MAE: `4,017,903`

3) Clean time-split C5 reference
- MLflow run: `e96a87091347453292c30bd45533b231`
- Overall MAE: `998,152`
- Treasury MAE: `710,263`
- Listing MAE: `6,862,957`

4) Two-stage time-split C5 reference
- MLflow run: `b3a587bd3a8244dca2720f6fcfa4769a`
- Overall MAE: `943,288`
- Treasury MAE: `681,869`
- Listing MAE: `6,268,830`

### Phase 0 Decision

- Keep `C5` two-stage (`run 4878...`) as the default non-image baseline to beat.
- Continue reporting both grouped and time-split results.

---

## 3. Success Gates For Phase 1 (Image Prep + First M1 Runs)

- Listing MAE must improve versus two-stage grouped baseline.
- Treasury MAE regression should remain near the prior tolerance band (`<~2-3%` preferred).
- Any gain should appear on both:
  - grouped split
  - source-aware time split
- Report required slices:
  - overall, treasury, listing
  - source site (`baania`, `hipflat`, `legacy_bania` when present)
  - has uploaded images vs no uploaded images
  - top property types

---

## 4. Phase 1 Preparation Checklist (Start)

### Data and Artifact Preparation

- [x] Baseline frozen and run IDs locked
- [x] Added image candidate manifest builder script
- [x] Added listing image quality audit script
- [x] Run image quality audit and publish JSON/MD
- [x] Build benchmark-aligned top-k image manifest
- [x] Confirm listing-key join coverage (`source + source_listing_id`) in manifest

### Feature Pipeline Preparation

- [x] Decide initial embedding encoder (`CLIP` or `DINOv2`)
- [x] Decide top-k policy (`k=1` vs `k=3`, default `k=3`)
- [x] Decide pooling policy (mean first)
- [x] Define fallback behavior for listings with no uploaded images

### Experiment Setup

- [x] Define `C5I` stage naming in trainer
- [x] Add MLflow params for image-manifest version and embedding version
- [x] Pre-register first M1 run IDs in this tracker

---

## 5. Immediate Commands (Phase 1 Prep)

Run from `gis-server/`.

```bash
uv run python -m scripts.audit_listing_images_quality \
  --dataset data/benchmarks/combined_sales_v1.parquet \
  --output-json data/benchmarks/listing_image_quality_v1.json \
  --output-md data/benchmarks/listing_image_quality_v1.md

uv run python -m scripts.extract_listing_image_embeddings \
  --dataset data/benchmarks/combined_sales_v1.parquet \
  --output data/benchmarks/listing_image_embedding_manifest_v1.parquet \
  --audit-json data/benchmarks/listing_image_embedding_manifest_v1_audit.json \
  --top-k 3 \
  --prefer-uploaded
```

### Phase 1 Prep Findings (Executed)

- Image quality audit outputs:
  - `gis-server/data/benchmarks/listing_image_quality_v1.json`
  - `gis-server/data/benchmarks/listing_image_quality_v1.md`
- Embedding manifest outputs:
  - `gis-server/data/benchmarks/listing_image_embedding_manifest_v1.parquet`
  - `gis-server/data/benchmarks/listing_image_embedding_manifest_v1_audit.json`
- Key findings:
  - listing rows: `513`
  - rows with selected top-k images: `477` (`93.0%` coverage)
  - selected image rows: `1,428`
  - selected uploaded rows: `1,158` (`81.1%` of selected)
  - mapping coverage for clean sources (`baania`, `hipflat`): `100%`


---

## 6. Notes

- This tracker is intentionally focused on execution order and gating.
- Keep appending run entries here as soon as Phase 1 experiments start.

### Locked Phase 1 Defaults

- Encoder: `openai/clip-vit-base-patch32`
- Top-k images per listing: `3`
- Listing pooling: mean pooling over selected images
- Fallback for no-image rows: zero embedding vector plus `has_image_embedding=0`
- Artifact outputs:
  - `gis-server/data/benchmarks/listing_image_embeddings_v1.parquet`
  - `gis-server/data/benchmarks/listing_image_embeddings_v1_audit.json`

### First M1 Runs (Registered)

- Grouped split comparison (`C5` vs `C5I`):
  - MLflow run: `5276dd07e0224e429f99406bcd3e94b9`
  - Output: `gis-server/models/combined_price_grouped_cv_c5_vs_c5i_m1_v1/stage_summary.json`
- Time split comparison (`C5` vs `C5I`):
  - MLflow run: `80ad8cee88b34572987750fd123caa84`
  - Output: `gis-server/models/combined_price_time_split_c5_vs_c5i_m1_v1/stage_summary.json`

### M1 Early Outcome (v1)

- Embedding build artifact:
  - `gis-server/data/benchmarks/listing_image_embeddings_v1.parquet`
  - `gis-server/data/benchmarks/listing_image_embeddings_v1_audit.json`
  - embedding dim: `768`
  - listing rows with embeddings: `387`

- Grouped split result:
  - `C5`: overall MAE `996,616`, listing MAE `4,017,903`, treasury MAE `814,572`
  - `C5I`: overall MAE `1,003,526`, listing MAE `4,079,253`, treasury MAE `818,202`
  - Interpretation: first image-integration pass did not beat baseline on grouped benchmark.

- Time split result:
  - `C5`: overall MAE `943,288`, listing MAE `6,268,830`, treasury MAE `681,869`
  - `C5I`: overall MAE `964,645`, listing MAE `6,668,176`, treasury MAE `684,672`
  - Interpretation: first image-integration pass also regressed on time split.

- Decision:
  - Keep `C5` two-stage as active leader.
  - Continue M1 iteration with stronger filtering/regularization and dimensionality reduction instead of promoting current `C5I`.
