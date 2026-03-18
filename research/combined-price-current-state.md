# Combined Price Prediction Current State

## Status Snapshot

- Date: 2026-03-13
- Branch: `feat/model-improvement-phase1`
- Dataset version: `combined_sales_v1`
- Current benchmark split: `grouped_cv_h3_res7_property_type`
- MLflow run: `c3677261fc0448c59624d74021b4716d`
- MLflow URL: `http://localhost:5001/#/experiments/1/runs/c3677261fc0448c59624d74021b4716d`

## What Was Completed

- Materialized a combined Treasury + listing modeling table at `gis-server/data/benchmarks/combined_sales_v1.parquet`
- Produced audit artifacts at `gis-server/data/benchmarks/combined_sales_v1_audit.json` and `gis-server/data/benchmarks/combined_sales_v1_audit.md`
- Built a stricter grouped split artifact at `gis-server/data/benchmarks/combined_sales_v1_grouped_cv_splits.parquet`
- Implemented CPU-feasible combined training pipeline with MLflow tracking in `gis-server/scripts/train_combined_price_model_mlflow.py`
- Rebuilt the combined benchmark after adding normalized Hipflat coverage and much higher uploaded-image coverage
- Re-ran `C1 -> C5` on the stricter grouped split and saved artifacts under `gis-server/models/combined_price_grouped_cv`

## Current Dataset Facts

- Total rows: `9,027`
- Treasury rows: `8,514`
- Listing rows: `513`
- Listing source coverage: `baania` + `hipflat`
- Listing exact-price usable rows: `513`
- Listing by source: `417` Baania, `96` Hipflat
- Listing image coverage: `93.0%` have image URLs, `75.4%` have uploaded images
- Listing metadata coverage from unit types is usable for `area_sqm`, `floors`, `bedrooms`, `bathrooms`, and `parking_spaces`

## Important Constraints

- Listing dates now span `2026-02-13` to `2026-03-13`, but still represent scrape-side asking-price snapshots rather than trustworthy market-time generalization
- Listing rows are project-level asking prices, not matched transaction outcomes
- Listing `land_area` remains excluded because current scraped unit land-area units are ambiguous
- Hipflat image coverage is still much weaker than Baania even after sync progress

## CPU Benchmark Results

| Stage | Features | Overall MAE | Overall % within 10% | Treasury MAE | Treasury % within 10% | Listing MAE | Listing % within 10% |
|---|---|---:|---:|---:|---:|---:|---:|
| C1 | common only | 1,330,362 | 20.39 | 1,105,165 | 20.79 | 5,067,830 | 13.84 |
| C2 | + source markers + missingness | 1,162,738 | 24.39 | 950,848 | 24.83 | 4,679,363 | 17.15 |
| C3 | + geo/H3/distance | 1,150,564 | 24.97 | 946,559 | 25.42 | 4,536,324 | 17.54 |
| C4 | + hex2vec | 1,010,854 | 29.54 | 798,731 | 30.26 | 4,531,354 | 17.74 |
| C5 | + listing metadata/text-lite | 1,004,694 | 29.00 | 800,960 | 29.47 | 4,385,973 | 21.25 |

## Delta Vs Prior Strict Grouped Run

- Listing MAE improved materially at every stage after the Hipflat expansion, roughly `16.7%` to `18.3%` better across `C1 -> C5`
- Best overall model is still `C5`, improving overall MAE from `1,013,377` to `1,004,694`
- `C4` also improved, from `1,028,791` to `1,010,854`
- Treasury-side MAE stayed roughly flat, which means the new gain came mainly from broader listing coverage rather than changing Treasury behavior

## Interpretation

- `C5` is still the best current overall CPU model under the stricter grouped benchmark
- The stricter grouped split is materially harder than the earlier split, which likely means it is a more honest benchmark
- `C2` still proves source-awareness is necessary
- `C4` and `C5` remain the strongest stages, so geo plus `hex2vec` plus listing metadata is still the right pre-image direction
- The new Hipflat rows produced a real listing-side gain, which validates the strategy of improving normalized listing coverage before escalating model complexity
- Listing-side error remains much worse than Treasury-side error, so the next leverage is still better data coverage and benchmark validity rather than rushing into HGT or image embeddings

## Legacy Expansion Check

- A separate experimental dataset variant was built at `gis-server/data/benchmarks/combined_sales_v1_legacy_salvage.parquet`
- It adds `5,149` rule-based legacy Baania salvage rows, bringing listing rows to `5,662`
- On the strict grouped benchmark, this legacy-expanded variant improved listing MAE substantially but made overall MAE much worse because the dataset mix changed heavily toward listing rows
- Current conclusion: keep the clean mixed benchmark as the main scoreboard; use the legacy-expanded dataset only for controlled experiments such as source weighting, listing-only analysis, or staged training

## Two-Stage Transfer Check

- Added two-stage support to `gis-server/scripts/train_combined_price_model_mlflow.py` so a listing-only legacy-heavy dataset can pretrain a booster before fold-level fine-tuning on the clean mixed benchmark
- First `C5` two-stage runs used `gis-server/data/benchmarks/listing_sales_v1_legacy_salvage.parquet` for pretraining and the clean grouped benchmark for fine-tuning
- MLflow runs:
  - unweighted pretrain: `20103a7020bc443b9e862fa13296ff17`
  - weighted pretrain: `dc730b4f8d3d48789fff04da35d62b45`
- Best two-stage result so far is the weighted-pretrain variant on overall MAE:
  - overall MAE `996,616`
  - treasury MAE `814,572`
  - listing MAE `4,017,903`
- Best listing MAE so far is the unweighted tuned `C5` variant:
  - overall MAE `1,010,171`
  - treasury MAE `832,336`
  - listing MAE `3,961,608`
- Interpretation:
  - tuned two-stage training is materially better than naive mixed legacy training and now slightly beats the clean benchmark on overall MAE
  - the best tuned variant keeps Treasury regression to about `1.7%`, which is within the earlier acceptable tolerance band, while still improving listing MAE by about `8.4%`
  - this is now the strongest overall result in the CPU-feasible path so far

## First Time-Split Check

- Added a first source-aware forward-chaining split at `gis-server/data/benchmarks/combined_sales_v1_time_split.parquet`
- Time grouping currently uses:
  - Treasury by `event_date` quarter
  - listings by scrape-day proxy from `event_date`
- Time-split MLflow runs:
  - clean `C5`: `e96a87091347453292c30bd45533b231`
  - best two-stage `C5`: `b3a587bd3a8244dca2720f6fcfa4769a`
- Time-split results:
  - clean `C5`: overall MAE `998,152`, treasury MAE `710,263`, listing MAE `6,862,957`
  - best two-stage `C5`: overall MAE `943,288`, treasury MAE `681,869`, listing MAE `6,268,830`
- Interpretation:
  - the two-stage winner still holds under the first time-aware benchmark, which is a strong positive sign
  - but listing time generalization is still weak and unstable because clean listings currently span only `3` scrape days with very small later holdouts
  - this means the current time split is useful as a realism check, but still too sparse to be treated as a final benchmark

## Honest Assessment

- The current model is promising, but not yet good enough to call production-good house price prediction
- It is now a much stronger research benchmark than before because:
  - the evaluation is more honest
  - the model is source-aware
  - legacy listing data is being used in a controlled way that actually helps
- The biggest remaining bottleneck is still data realism on the listing side, not raw model complexity

## Recommended Next Work

1. Expand clean listing time depth and source breadth so the time-aware benchmark becomes trustworthy
2. Validate and stress-test the new best two-stage recipe under additional benchmark slices
3. Improve listing timestamp semantics if any better per-source date fields exist
4. Improve image upload coverage before attempting `M1`
5. Test segmented benchmarks by property type if the broader listing table becomes available
6. Only revisit HGT after the non-image grouped benchmark is stronger and listing coverage is materially better

## Recommended Next Two Steps

### Step 1 - Build A Time-Aware Listing Benchmark

- Priority: highest
- Why now: the first time-split check was useful and the two-stage winner survived it, but the listing-side time benchmark is still too shallow to trust fully
- Deliverables:
  - add more clean listing snapshots by date and source
  - rebuild the source-aware time split with deeper listing history
  - rerun the clean baseline and the current best two-stage recipe under the stronger time-aware benchmark
- Success signal:
  - train/validation/test windows are explicit and materially less sparse
  - listing-side time-split metrics stop being dominated by tiny holdout slices

### Step 2 - Expand Listing Coverage

- Priority: second
- Why now: broader clean normalized listing coverage still improves the base benchmark directly and will also make the new two-stage winner more trustworthy
- Deliverables:
  - add more listing snapshots and/or additional normalized listing sources
  - rebuild `combined_sales_v1` into a broader next dataset version
  - refresh audit artifacts with row counts, source mix, duplicate risk, and image coverage
- Success signal:
  - materially more clean listing rows than the current `513`
  - more than one listing source or more than one listing snapshot date with defensible event semantics

### Step 3 - Stress-Test The New Two-Stage Leader

- Priority: third
- Why now: we now have a plausible leading recipe and should verify it is not a fragile win tied to one stage or one weighting choice
- Deliverables:
  - compare against additional sliced reports and stability checks
  - test whether the best recipe remains ahead across source and property-type segments
  - preserve the exact MLflow run and config as the new reference candidate
- Success signal:
  - the win remains robust rather than depending on one or two anomalous folds

## Help Needed From User

### For Step 1

- confirm which additional listing sources we can legally and practically use next
- point me to any existing raw dumps, databases, buckets, or machines that contain more listing snapshots or non-Baania listing data
- clarify whether the larger legacy `real_estate_listings` table is acceptable as an interim expansion source

### For Step 2

- confirm the best available date semantics you trust for each source (`scraped_at`, published date, updated date, or another proxy)
- point me to any historical scrape schedule notes so I can define realistic time windows
- tell me whether you want the first time-aware benchmark to optimize for strict realism or for maximum comparable sample size
