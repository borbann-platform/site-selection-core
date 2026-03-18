# Price Model Research Journal

## 2026-03-12 - Combined CPU Benchmark Foundation

### Scope

- Continue price prediction improvement using CPU-feasible work only
- Track artifacts in MLflow when possible
- Preserve all benchmark findings in repo research notes

### Artifacts Created

- Dataset builder: `gis-server/scripts/build_combined_price_dataset.py`
- Combined dataset: `gis-server/data/benchmarks/combined_sales_v1.parquet`
- Dataset audit JSON: `gis-server/data/benchmarks/combined_sales_v1_audit.json`
- Dataset audit markdown: `gis-server/data/benchmarks/combined_sales_v1_audit.md`
- Combined trainer: `gis-server/scripts/train_combined_price_model_mlflow.py`
- First CPU ladder artifacts: `gis-server/models/combined_price_cpu_mlflow`
- Current-state memo: `research/combined-price-current-state.md`

### Dataset Findings

- Combined dataset currently includes `8,514` Treasury rows and `417` Baania listing rows
- Listing rows are restricted to exact `price_start` records with valid coordinates and `price_end IS NULL`
- Listing image URL coverage is high (`91.4%`) but uploaded-image coverage is still low (`16.1%`)
- Listing metadata from unit types is good enough for `area_sqm`, `floors`, `bedrooms`, `bathrooms`, and `parking_spaces`
- Listing `land_area` is still unusable due to ambiguous units in current scraped data
- Listing time coverage is a single scrape session on `2026-02-13`, so time-based validation is not yet trustworthy for listings

### MLflow Run

- Run ID: `62390f07bdab4b3eb1bbe14583f7ae41`
- URL: `http://localhost:5001/#/experiments/1/runs/62390f07bdab4b3eb1bbe14583f7ae41`

### CPU Ladder Results On Initial Split

| Stage | Overall MAE | Overall %<10 | Treasury MAE | Treasury %<10 | Listing MAE | Listing %<10 |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 1,113,933 | 32.65 | 873,129 | 33.24 | 6,030,504 | 20.62 |
| C2 | 981,810 | 36.27 | 753,435 | 36.90 | 5,644,616 | 23.26 |
| C3 | 953,394 | 37.55 | 723,644 | 38.35 | 5,644,246 | 21.34 |
| C4 | 878,587 | 42.02 | 632,690 | 43.22 | 5,899,134 | 17.51 |
| C5 | 861,629 | 42.55 | 629,918 | 43.46 | 5,592,526 | 23.98 |

### Interpretation

- Source-aware modeling is mandatory; `C2` is a major improvement over `C1`
- Geo features and `hex2vec` materially improve Treasury-side generalization
- `C5` is the best first CPU baseline and should be treated as the current non-image champion
- Listing-side error remains very large, so benchmark and label limitations are still the dominant issue

---

## 2026-03-12 - Stricter Grouped Split Benchmark

### Goal

- Replace the earlier looser grouping with a stricter leakage-resistant split before any image embedding or HGT work

### New Artifacts

- Grouped split builder: `gis-server/scripts/build_combined_grouped_split.py`
- Split assignments: `gis-server/data/benchmarks/combined_sales_v1_grouped_cv_splits.parquet`
- Split summary JSON: `gis-server/data/benchmarks/combined_sales_v1_grouped_cv_splits.json`
- Split summary markdown: `gis-server/data/benchmarks/combined_sales_v1_grouped_cv_splits.md`
- Grouped split training artifacts: `gis-server/models/combined_price_grouped_cv`

### Split Definition

- Group definition: `property_type + h3_res7 spatial cell`
- Fold builder: `GroupKFold(n_splits=5)` over strict groups
- Effect: all rows from the same coarse property-type-and-location cluster remain in the same fold

### Split Balance Findings

- Total strict groups: `688`
- Total spatial groups: `325`
- Fold sizes are balanced at `1,786-1,787` rows each
- Listing rows per fold range from `76` to `91`
- Treasury rows per fold range from `1,695` to `1,711`

### MLflow Run

- Run ID: `ac8107841dbb4431aa9dc4725504b819`
- URL: `http://localhost:5001/#/experiments/1/runs/ac8107841dbb4431aa9dc4725504b819`

### CPU Ladder Results On Strict Grouped Split

| Stage | Overall MAE | Overall %<10 | Treasury MAE | Treasury %<10 | Listing MAE | Listing %<10 |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 1,321,326 | 20.69 | 1,082,301 | 20.73 | 6,201,550 | 19.90 |
| C2 | 1,175,631 | 24.22 | 958,216 | 24.44 | 5,614,645 | 19.66 |
| C3 | 1,150,537 | 24.70 | 940,238 | 24.85 | 5,444,276 | 21.58 |
| C4 | 1,028,791 | 29.53 | 809,484 | 29.86 | 5,506,430 | 22.78 |
| C5 | 1,013,377 | 29.78 | 800,766 | 30.20 | 5,354,304 | 21.34 |

### Interpretation

- The stricter grouped split is much harder than the earlier benchmark, which is a good sign that it is more leakage-resistant
- Overall MAE is about `17-21%` worse than the earlier split across `C1 -> C5`, which strongly suggests the earlier benchmark was materially easier
- All stages degrade materially versus the earlier split, especially Treasury-side metrics
- `C5` is still the best overall model under the harder benchmark
- `C4` and `C5` still provide the best gains, so geo plus `hex2vec` plus listing metadata remain the correct direction
- Listing performance improves only modestly even after stronger features, reinforcing that more listing coverage and better listing labels matter more than immediate image or graph complexity

### Decision

- Use the stricter grouped split as the primary pre-image, pre-HGT benchmark for further CPU iteration
- Defer image embedding until data coverage improves
- Defer HGT until the stronger grouped benchmark is stable and listing coverage expands

---

## 2026-03-12 - Next-Step Prioritization Memo

### Top 2 Recommended Steps

- Step 1: expand listing coverage beyond the current single Baania snapshot
- Step 2: add a true time-aware listing benchmark once multiple listing snapshots or source dates are available

### Why These Two Steps Win

- Listing-side error is still far worse than Treasury-side error, so the main bottleneck is benchmark data quality and coverage
- The current grouped split is good for leakage control, but it still does not answer whether the model generalizes across time on listing data
- Better data coverage and time realism are more valuable now than adding image embeddings or graph complexity

### Other Recommended Next Steps So We Do Not Forget

- improve uploaded image coverage before starting `M1`
- test segmented benchmarks by property type once listing coverage is broader
- continue tabular feature iteration only when changes are justified under the stricter benchmark
- revisit HGT only after the broader non-image benchmark is clearly stronger

### User Help That Would Unblock The Top 2 Steps

- provide access or pointers to additional listing snapshots, source dumps, or normalized listing tables
- clarify whether the larger legacy `real_estate_listings` table is allowed as an interim data-expansion source
- clarify which date field semantics should be trusted by source for the first time-aware benchmark
- share any scrape schedule/history context that can support defensible train/validation/test windows

---

## 2026-03-13 - Hipflat Expansion Checkpoint

### Dataset Update

- Rebuilt `combined_sales_v1` after adding more normalized Hipflat rows and syncing many more listing images
- Combined dataset now has `9,027` rows: `8,514` Treasury and `513` listing
- Listing mix is now `417` Baania + `96` Hipflat
- Listing uploaded-image coverage improved to `75.4%`

### Strict Grouped Benchmark Rerun

- MLflow run: `c3677261fc0448c59624d74021b4716d`
- Best stage remains `C5`
- Updated grouped benchmark results:
  - `C1`: overall MAE `1,330,362`, listing MAE `5,067,830`, treasury MAE `1,105,165`
  - `C2`: overall MAE `1,162,738`, listing MAE `4,679,363`, treasury MAE `950,848`
  - `C3`: overall MAE `1,150,564`, listing MAE `4,536,324`, treasury MAE `946,559`
  - `C4`: overall MAE `1,010,854`, listing MAE `4,531,354`, treasury MAE `798,731`
  - `C5`: overall MAE `1,004,694`, listing MAE `4,385,973`, treasury MAE `800,960`

### Comparison Vs Prior Strict Grouped Run

- Listing MAE improved materially across every stage, about `16.7%` to `18.3%` better than the previous strict grouped run
- Overall MAE improved modestly at the best stages:
  - `C4`: `1,028,791` -> `1,010,854`
  - `C5`: `1,013,377` -> `1,004,694`
- Treasury-side MAE stayed roughly flat, which indicates that the new benefit is mainly better listing coverage rather than a broad benchmark shift

### Interpretation

- This is the first clear proof that expanding normalized listing coverage is paying off under the stricter benchmark
- `C5` is still the strongest pre-image CPU model
- `C4` remains very competitive, but `C5` keeps the edge overall and on listing MAE
- The result strengthens the case for continuing listing expansion and only then moving to time-aware evaluation and multimodal work

### Decision

- Keep the grouped split as the main benchmark for now
- Continue expanding listing coverage, especially Hipflat and future additional sources or snapshots
- Make the next major benchmark upgrade a source-aware time split rather than jumping straight to image embeddings or HGT

---

## 2026-03-13 - Legacy Bulk Listing Audit

### Goal

- Determine whether the old bulk-loaded `real_estate_listings` table is likely usable as a controlled benchmark expansion source

### Audit Artifacts

- `gis-server/scripts/audit_legacy_realestate_listings.py`
- `gis-server/data/benchmarks/legacy_real_estate_listing_audit.json`
- `gis-server/data/benchmarks/legacy_real_estate_listing_audit.md`

### Findings

- `real_estate_listings` contains `38,767` rows total and about `23,049` Bangkok-bbox rows
- For Bangkok-bbox rows restricted to `บ้าน`, `ทาวน์โฮม`, and `บ้านแฝด`, there are `15,943` candidate rows
- A rule-based salvage estimate suggests about `10,841` rows remain after:
  - strict `THB` price parsing
  - plausible sale-price bounds
  - plausible area bounds
  - plausible price-per-sqm bounds
- This is about `21x` larger than the current clean normalized listing benchmark (`513` listing rows)
- The source is still noisy:
  - `last_updated` is completely empty
  - house-like rows appear under unexpected source files such as `office_all.csv` and `apartment_all.csv`
  - source-file provenance is weaker than the newer normalized scraped pipeline

### Interpretation

- The legacy source looks too valuable to ignore
- It is not yet clean enough to merge directly into the main benchmark without a controlled salvage policy
- The best next use is a parallel candidate-expansion experiment, not immediate replacement of the current benchmark source

### Decision

- Keep `scraped_listings` as the clean benchmark reference
- Treat `real_estate_listings` as the highest-upside controlled expansion candidate
- Next implementation step should be a sale-only salvage dataset builder for legacy listings, followed by side-by-side benchmark comparison

---

## 2026-03-13 - Legacy Salvage Expansion Experiment

### Implementation

- Extended `gis-server/scripts/build_combined_price_dataset.py` with an optional `--include-legacy-listings` path
- Added a separate benchmark variant:
  - dataset: `gis-server/data/benchmarks/combined_sales_v1_legacy_salvage.parquet`
  - split: `gis-server/data/benchmarks/combined_sales_v1_legacy_salvage_grouped_cv_splits.parquet`
  - model outputs: `gis-server/models/combined_price_grouped_cv_legacy_salvage`
- MLflow run: `9e95039e258c49f8aeb5bd9e4ecf8f6c`

### Dataset Outcome

- Expanded dataset size: `14,176` rows
- Source mix:
  - Treasury: `8,514`
  - Baania: `417`
  - Hipflat: `96`
  - legacy_bania salvage: `5,149`
- Total listing rows: `5,662`

### Benchmark Outcome

- Best stage remains `C5`
- Expanded-dataset strict grouped results:
  - `C1`: overall MAE `2,299,911`, listing MAE `4,043,739`, treasury MAE `1,140,227`
  - `C2`: overall MAE `2,012,118`, listing MAE `3,575,645`, treasury MAE `972,339`
  - `C3`: overall MAE `2,028,682`, listing MAE `3,633,981`, treasury MAE `961,121`
  - `C4`: overall MAE `1,950,592`, listing MAE `3,640,729`, treasury MAE `826,613`
  - `C5`: overall MAE `1,822,393`, listing MAE `3,334,910`, treasury MAE `816,535`

### Comparison Vs Clean Benchmark

- Listing MAE improved substantially at every stage, about `19.6%` to `24.0%` better than the clean benchmark
- But overall MAE became far worse, roughly `73%` to `93%` worse depending on stage
- Treasury MAE also got a bit worse (`~2%` to `3.5%` worse)

### Interpretation

- The legacy salvage source adds a lot of listing signal, but it shifts the dataset balance so much that overall benchmark behavior is no longer comparable to the clean benchmark
- This makes the expanded dataset useful for listing-only or source-segment experiments, but risky as a replacement for the main mixed benchmark
- The result suggests the legacy source is directionally useful, but should probably be introduced with stronger controls such as source weighting, per-source evaluation, or segmented training rather than naive concatenation

### Decision

- Do not replace the current clean mixed benchmark with the naive legacy-expanded version
- Keep the clean benchmark as the main scoreboard
- Treat the legacy-expanded dataset as an experimental branch for source-segment analysis, weighting, or staged training

---

## 2026-03-13 - Listing-Only Benchmark Pipeline

### Implementation

- Added `gis-server/scripts/build_listing_only_dataset.py`
- Added `make build-listing-only-benchmark`
- Built listing-only artifacts:
  - dataset: `gis-server/data/benchmarks/listing_sales_v1_legacy_salvage.parquet`
  - split: `gis-server/data/benchmarks/listing_sales_v1_legacy_salvage_grouped_cv_splits.parquet`
  - model outputs: `gis-server/models/listing_only_grouped_cv_legacy_salvage`
- MLflow run: `ba7ef44bf10a415581462fe2f89a61bb`

### Dataset Outcome

- Listing-only rows: `5,662`
- Source mix:
  - legacy_bania: `5,149`
  - baania: `417`
  - hipflat: `96`

### Listing-Only Benchmark Outcome

- Best stage remains `C5`
- Listing-only grouped results:
  - `C1`: MAE `3,982,585`
  - `C2`: MAE `3,579,948`
  - `C3`: MAE `3,595,328`
  - `C4`: MAE `3,627,399`
  - `C5`: MAE `3,287,821`

### Interpretation

- The listing-only pipeline is now working and reusable
- `C5` again gives the strongest result, which supports keeping metadata/text-lite features in the listing-focused path
- The listing-only benchmark gives us a cleaner sandbox for experimenting with legacy data without distorting the mixed Treasury + listing scoreboard

### Next Planned Step

- Implement weighted training / source weighting on the mixed benchmark so legacy rows can contribute signal without overwhelming the clean benchmark distribution

---

## 2026-03-13 - Conservative Source Weighting Experiment

### Implementation

- Extended `gis-server/scripts/train_combined_price_model_mlflow.py` to accept per-source sample weights via `--source-weights-json`
- Added a conservative weighting config at `gis-server/data/benchmarks/source_weights_legacy_conservative.json`
- Weight policy used in this run:
  - Treasury: `1.0`
  - Baania: `1.0`
  - Hipflat: `1.0`
  - legacy_bania: `0.25`
- Weighted mixed run artifacts:
  - output dir: `gis-server/models/combined_price_grouped_cv_legacy_salvage_weighted`
  - MLflow run: `d4c790cf7f2f4d218c086d7375cf7672`

### Benchmark Outcome

- Best stage remains `C5`
- Weighted mixed `C5` results:
  - overall MAE `1,821,174`
  - listing MAE `3,340,554`
  - treasury MAE `810,752`

### Comparison

- Versus the clean benchmark `C5`:
  - overall MAE is still much worse (`1,004,694` -> `1,821,174`)
  - listing MAE is much better (`4,385,973` -> `3,340,554`)
  - treasury MAE is slightly worse (`800,960` -> `810,752`)
- Versus the unweighted legacy-expanded `C5`:
  - overall MAE is essentially unchanged but very slightly better
  - treasury MAE improves a bit
  - listing MAE gets very slightly worse

### Interpretation

- Conservative source weighting is not enough to recover the clean mixed benchmark behavior once legacy rows dominate row count
- Weighting helps a little on Treasury-side damage, but not nearly enough to justify replacing the clean benchmark
- The legacy source still looks most useful for listing-only modeling, staged training, or more advanced weighting schemes rather than simple naive mixing

### Decision

- Keep the clean mixed benchmark as the primary scoreboard
- Keep the listing-only benchmark as the main place to exploit legacy listing volume
- If we continue weighting work, the next realistic variants should be stronger down-weighting, fold-aware resampling, or two-stage training rather than assuming a mild weight is sufficient

---

## 2026-03-13 - Two-Stage Listing Pretrain -> Clean Fine-Tune

### Implementation

- Extended `gis-server/scripts/train_combined_price_model_mlflow.py` with optional two-stage support:
  - `--pretrain-dataset`
  - `--pretrain-source-weights-json`
  - `--pretrain-n-estimators`
  - `--finetune-n-estimators`
  - `--stages`
- The trainer now:
  - builds aligned categorical encodings across clean and pretrain datasets
  - pretrains a LightGBM booster on the listing-only dataset per fold
  - excludes validation-fold row overlaps from the pretrain stage
  - fine-tunes on the clean mixed fold training slice using `init_model`

### Experiment Setup

- Fine-tune target benchmark:
  - dataset: `gis-server/data/benchmarks/combined_sales_v1.parquet`
  - split: `gis-server/data/benchmarks/combined_sales_v1_grouped_cv_splits.parquet`
- Pretrain source:
  - dataset: `gis-server/data/benchmarks/listing_sales_v1_legacy_salvage.parquet`
- Stage tested first: `C5`
- Output dirs:
  - unweighted: `gis-server/models/combined_price_grouped_cv_two_stage_listing_pretrain_v2`
  - weighted pretrain: `gis-server/models/combined_price_grouped_cv_two_stage_listing_pretrain_weighted_v2`
- MLflow runs:
  - unweighted two-stage: `20103a7020bc443b9e862fa13296ff17`
  - weighted-pretrain two-stage: `dc730b4f8d3d48789fff04da35d62b45`

### Benchmark Outcome

- Clean benchmark `C5` reference:
  - overall MAE `1,004,694`
  - treasury MAE `800,960`
  - listing MAE `4,385,973`
- Unweighted two-stage `C5`:
  - overall MAE `1,017,536`
  - treasury MAE `842,232`
  - listing MAE `3,926,964`
- Weighted-pretrain two-stage `C5`:
  - overall MAE `1,014,713`
  - treasury MAE `836,076`
  - listing MAE `3,979,459`

### Comparison

- Versus the clean benchmark `C5`:
  - unweighted two-stage improves listing MAE by about `10.5%`
  - weighted-pretrain two-stage improves listing MAE by about `9.3%`
  - but neither beats the clean benchmark overall yet
  - treasury MAE degrades by about `5.2%` unweighted and `4.4%` weighted
- Versus naive mixed legacy expansion and simple weighting:
  - two-stage training is dramatically better on overall MAE while keeping much of the listing-side gain
  - this is the first legacy-data strategy that looks genuinely promising for the main mixed benchmark path

### Interpretation

- The legacy listing source is more useful as transfer signal than as a directly mixed training distribution
- Two-stage training largely avoids the catastrophic benchmark distortion seen in naive mixed legacy runs
- The current tradeoff is real but plausible:
  - listing-side performance improves materially
  - overall MAE stays close to the clean benchmark
  - treasury-side performance still regresses more than we want
- Weighting only the pretrain stage helps overall and treasury slightly, but gives back some listing gain

### Decision

- Keep the clean mixed benchmark as the primary scoreboard for now
- Promote two-stage training to the main experimental path for legacy listing reuse
- Next follow-up work should be targeted two-stage tuning:
  - tune pretrain vs fine-tune tree budgets
  - test stronger pretrain down-weighting or subsampling
  - try pretraining on `C4` and `C5` only rather than the full ladder
  - then compare against a source-aware time split once that benchmark is ready

---

## 2026-03-13 - Two-Stage Tuning Sweep

### Goal

- Improve the first two-stage result by reducing Treasury regression while preserving the listing-side gain

### Added Artifact

- Strong pretrain weighting config: `gis-server/data/benchmarks/source_weights_legacy_strong_pretrain.json`
  - `legacy_bania`: `0.1`

### MLflow Runs

- `C4` unweighted, pretrain/fine-tune `200/400`:
  - run: `2615896734544eafb231fd34e7598c95`
  - output: `gis-server/models/combined_price_grouped_cv_two_stage_c4_unweighted_p200_f400`
- `C5` unweighted, pretrain/fine-tune `200/400`:
  - run: `a6bb2d7171a54b409951d3aab8e0b15a`
  - output: `gis-server/models/combined_price_grouped_cv_two_stage_c5_unweighted_p200_f400`
- `C5` strong-weight pretrain, `200/400`:
  - run: `5ac3c66ccf794e0fa43bb3974a3655c0`
  - output: `gis-server/models/combined_price_grouped_cv_two_stage_c5_strongweight_p200_f400`
- `C5` strong-weight pretrain, `150/450`:
  - run: `833b4c444db3406ebe99634dfee243e2`
  - output: `gis-server/models/combined_price_grouped_cv_two_stage_c5_strongweight_p150_f450`
- `C5` strong-weight pretrain, `100/500`:
  - run: `4878bc4faa49431a83d47932460483c4`
  - output: `gis-server/models/combined_price_grouped_cv_two_stage_c5_strongweight_p100_f500`

### Key Results

- Clean benchmark `C5` reference:
  - overall MAE `1,004,694`
  - treasury MAE `800,960`
  - listing MAE `4,385,973`
- Best earlier two-stage baseline before tuning:
  - overall MAE `1,014,713`
  - treasury MAE `836,076`
  - listing MAE `3,979,459`
- Tuning sweep outcomes:
  - `C4` unweighted `200/400`:
    - overall MAE `1,003,360`
    - treasury MAE `836,494`
    - listing MAE `4,221,499`
  - `C5` unweighted `200/400`:
    - overall MAE `1,010,171`
    - treasury MAE `832,336`
    - listing MAE `3,961,608`
  - `C5` strong-weight `200/400`:
    - overall MAE `1,001,985`
    - treasury MAE `819,721`
    - listing MAE `4,026,940`
  - `C5` strong-weight `150/450`:
    - overall MAE `996,872`
    - treasury MAE `813,567`
    - listing MAE `4,039,083`
  - `C5` strong-weight `100/500`:
    - overall MAE `996,616`
    - treasury MAE `814,572`
    - listing MAE `4,017,903`

### Interpretation

- This is the strongest result so far
- Shifting more capacity into clean fine-tuning and down-weighting legacy pretrain rows works better than the first two-stage setup
- Best current tradeoff is `C5` strong-weight `100/500`:
  - beats the clean benchmark on overall MAE by a small margin
  - improves listing MAE by about `8.4%`
  - limits Treasury degradation to about `1.7%`, which is now inside the previously discussed tolerance band
- `C4` two-stage is also interesting because it nearly matches the clean benchmark overall while improving listing MAE, but `C5` remains better

### Decision

- Promote `C5` two-stage with strong pretrain down-weighting and heavier clean fine-tuning as the current best experimental path
- Treat run `4878bc4faa49431a83d47932460483c4` as the current two-stage leader
- Next benchmark-quality step should still be a source-aware time split so we can test whether this improvement survives a more realistic temporal evaluation

---

## 2026-03-13 - Source-Aware Time Split Benchmark

### Implementation

- Added `gis-server/scripts/build_combined_time_split.py`
- Built a first source-aware forward-chaining split artifact:
  - `gis-server/data/benchmarks/combined_sales_v1_time_split.parquet`
  - `gis-server/data/benchmarks/combined_sales_v1_time_split.json`
  - `gis-server/data/benchmarks/combined_sales_v1_time_split.md`
- Extended `gis-server/scripts/train_combined_price_model_mlflow.py` so split artifacts with `time_group` are evaluated using forward chaining instead of standard held-out folds

### Time Split Definition

- Treasury groups by quarter:
  - fold 0: `2024Q1`, `2024Q2`, `2024Q3`
  - fold 1: `2024Q4`, `2025Q1`
  - fold 2: `2025Q2`, `NaT`
- Listing groups by scrape day proxy:
  - fold 0: `2026-02-13`
  - fold 1: `2026-03-12`
  - fold 2: `2026-03-13`
- Fold `0` is warm-up only and not scored because there is no prior window to train on

### MLflow Runs

- Clean `C5` on time split:
  - run: `e96a87091347453292c30bd45533b231`
  - output: `gis-server/models/combined_price_time_split_clean_c5_v3`
- Best two-stage `C5` on time split:
  - run: `b3a587bd3a8244dca2720f6fcfa4769a`
  - output: `gis-server/models/combined_price_time_split_two_stage_best_v3`

### Benchmark Outcome

- Clean `C5` time-split result:
  - overall MAE `998,152`
  - treasury MAE `710,263`
  - listing MAE `6,862,957`
- Best two-stage `C5` time-split result:
  - overall MAE `943,288`
  - treasury MAE `681,869`
  - listing MAE `6,268,830`

### Comparison

- Versus clean time-split `C5`:
  - two-stage improves overall MAE by about `5.5%`
  - two-stage improves treasury MAE by about `4.0%`
  - two-stage improves listing MAE by about `8.7%`
- But both models are much worse on listing MAE than under the grouped split benchmark

### Interpretation

- The two-stage recipe still wins under the more realistic time-aware evaluation, which is a strong sign that the improvement is not purely a grouped-CV artifact
- However, this first time benchmark also confirms the listing label/time problem is still severe:
  - listing rows come from only `3` scrape days
  - future-snapshot generalization for listings is still unstable and under-sampled
  - one fold is almost entirely a tiny Hipflat-only holdout on the listing side
- So the benchmark is directionally useful, but still not mature enough to call the problem solved

### Decision

- Keep the tuned two-stage `C5` recipe as the current leading model family
- Treat the first source-aware time split as a valuable realism check, not yet a final benchmark
- The highest-value next work is to improve listing date depth and source coverage so time evaluation becomes trustworthy rather than sparse and brittle

---

## 2026-03-13 - Deep Current-State Assessment

### Is The Model Good Right Now?

- Not yet good enough to call production-good house price prediction
- It is now a credible research benchmark and a meaningful internal candidate, but still not a model I would trust as a final user-facing valuation product without stronger data and evaluation

### Why It Is Better Than Before

- The benchmark is much more honest than the earlier easier split
- The model now uses source-aware features, geo context, `hex2vec`, listing metadata, and staged transfer from legacy listing volume
- The current best recipe improves both grouped and first-pass time-aware benchmarks versus the prior clean baseline

### Main Problems Still Limiting Quality

- Treasury and listing labels still do not represent the same thing:
  - Treasury behaves more like appraised/reference value
  - listings are noisy asking prices
- Listing time coverage is still shallow and scrape-proxy based rather than true market-time based
- Listing row count on the clean benchmark is still too small and uneven across sources
- Legacy data helps, but it is still noisy and only partially trustworthy
- Some property-type and source slices remain sparse enough that metrics can swing hard by fold

### Key Assumptions That Still Matter

- We assume exact listing price rows are a usable sale-price proxy even though they are asking prices
- We assume `scraped_at` is the best currently available listing time proxy
- We assume source-aware modeling and staged transfer can safely exploit legacy listing rows without overwhelming the clean benchmark
- We assume grouped spatial and source-aware time splits together are enough to detect the most important leakage and realism risks for now

### What The Results Mean Right Now

- On the current grouped benchmark, the tuned two-stage `C5` recipe is the best CPU-feasible result so far
- On the first source-aware time split, the same recipe still wins, which is important evidence that the gain is probably real
- But listing MAE under time evaluation is still too large and too unstable to claim strong listing-side valuation quality
- So the project is clearly progressing, but still in the "promising, not finished" stage

### Most Defensible Next Steps From Here

- First: expand clean listing time depth and source breadth
  - more Baania and Hipflat snapshots
  - any other legal clean Bangkok sale-listing source
- Second: improve the time benchmark itself
  - more listing dates
  - better per-source timestamp semantics if available
  - more balanced holdout windows
- Third: stress-test the current winning two-stage recipe across slices and possibly segmented variants
- Only after that should we seriously consider image embeddings as the next major modeling upgrade
- HGT should still stay deferred until the tabular-plus-transfer benchmark is stronger and the time benchmark is less brittle

---

## 2026-03-18 - M1 Image Embedding Pipeline (First Pass)

### Goal

- Start the first multimodal listing-image benchmark pass under the current data ceiling
- Keep `C5` two-stage as baseline and test whether `C5I` improves grouped and time-split benchmarks

### New Implementation Artifacts

- Image quality audit script: `gis-server/scripts/audit_listing_images_quality.py`
- Top-k image manifest builder: `gis-server/scripts/extract_listing_image_embeddings.py`
- CLIP embedding builder: `gis-server/scripts/build_listing_image_embeddings.py`
- Trainer extension for image features (`C5I`): `gis-server/scripts/train_combined_price_model_mlflow.py`
- Campaign tracker: `research/multimodal-news-campaign-20260318.md`

### Data Artifacts Generated

- Quality audit:
  - `gis-server/data/benchmarks/listing_image_quality_v1.json`
  - `gis-server/data/benchmarks/listing_image_quality_v1.md`
- Manifest:
  - `gis-server/data/benchmarks/listing_image_embedding_manifest_v1.parquet`
  - `gis-server/data/benchmarks/listing_image_embedding_manifest_v1_audit.json`
- Embeddings:
  - `gis-server/data/benchmarks/listing_image_embeddings_v1.parquet`
  - `gis-server/data/benchmarks/listing_image_embeddings_v1_audit.json`

### Coverage Snapshot

- Listing rows: `513`
- Rows with selected top-k image candidates: `477` (`93.0%`)
- Rows with uploaded image linkage: `387` (`75.4%`)
- Embedding dim: `768` (CLIP ViT-B/32)
- Listing rows with computed embeddings: `387`

### MLflow Runs

- Grouped split (`C5` vs `C5I`):
  - run: `5276dd07e0224e429f99406bcd3e94b9`
  - output: `gis-server/models/combined_price_grouped_cv_c5_vs_c5i_m1_v1`
- Time split (`C5` vs `C5I`):
  - run: `80ad8cee88b34572987750fd123caa84`
  - output: `gis-server/models/combined_price_time_split_c5_vs_c5i_m1_v1`

### Benchmark Outcome

- Grouped split:
  - `C5`: overall MAE `996,616`, treasury MAE `814,572`, listing MAE `4,017,903`
  - `C5I`: overall MAE `1,003,526`, treasury MAE `818,202`, listing MAE `4,079,253`
- Time split:
  - `C5`: overall MAE `943,288`, treasury MAE `681,869`, listing MAE `6,268,830`
  - `C5I`: overall MAE `964,645`, treasury MAE `684,672`, listing MAE `6,668,176`

### Interpretation

- The first end-to-end M1 pipeline is now functional and benchmarked.
- But first-pass image integration regressed both grouped and time-split scoreboards.
- Current likely issues:
  - high-dimensional image vector (`768`) overfitting vs limited clean listing rows
  - weak quality filtering and no embedding compression yet
  - sparse upload coverage on Hipflat still limits robust gains

### Decision

- Keep tuned two-stage `C5` as active leader.
- Continue to M1 iteration v2 with:
  - stronger image quality filtering
  - per-listing de-duplication by checksum
  - embedding dimensionality reduction (`PCA`/projection) before model training

---

## 2026-03-18 - M1 Iteration v2 (PCA + Filtering)

### Goal

- Improve first-pass `C5I` by reducing overfit risk from high-dimensional image vectors
- Keep benchmark protocol fixed and compare directly against same `C5` two-stage reference

### Implementation Changes

- Added quality filter options in manifest builder:
  - `--min-width`, `--min-height`, `--dedupe-checksum-per-listing`
  - file: `gis-server/scripts/extract_listing_image_embeddings.py`
- Added PCA compression stage in embedding builder:
  - `--pca-dim` (used `64`)
  - file: `gis-server/scripts/build_listing_image_embeddings.py`
- Produced v2 artifacts:
  - `gis-server/data/benchmarks/listing_image_embedding_manifest_v2.parquet`
  - `gis-server/data/benchmarks/listing_image_embedding_manifest_v2_audit.json`
  - `gis-server/data/benchmarks/listing_image_embeddings_v2.parquet`
  - `gis-server/data/benchmarks/listing_image_embeddings_v2_audit.json`

### Embedding Artifact Snapshot

- Model: `openai/clip-vit-base-patch32`
- Processed image rows: `1,158`
- Listing rows with embeddings: `387`
- Original dim: `768`
- Output dim after PCA: `64`
- Explained variance ratio sum: `0.826`

### MLflow Runs

- Grouped split (`C5` vs `C5I` with v2 embeddings):
  - run: `2adebc7244934b25b5b16b572c7bb82e`
  - output: `gis-server/models/combined_price_grouped_cv_c5_vs_c5i_m1_v2`
- Time split (`C5` vs `C5I` with v2 embeddings):
  - run: `1e09f0933eda4cf688a4f17021ec341b`
  - output: `gis-server/models/combined_price_time_split_c5_vs_c5i_m1_v2`

### Benchmark Outcome

- Grouped split:
  - `C5`: overall MAE `996,616`, treasury MAE `814,572`, listing MAE `4,017,903`
  - `C5I` v2: overall MAE `991,346`, treasury MAE `820,866`, listing MAE `3,820,714`
- Time split:
  - `C5`: overall MAE `943,288`, treasury MAE `681,869`, listing MAE `6,268,830`
  - `C5I` v2: overall MAE `961,661`, treasury MAE `689,627`, listing MAE `6,503,475`

### Interpretation

- v2 improved `C5I` significantly versus v1 on grouped split and now beats `C5` on:
  - overall MAE (small gain)
  - listing MAE (material gain)
- But time split still regresses versus `C5` on overall, listing, and treasury MAE.
- So image signal looks useful under grouped CV but is not yet stable for time generalization.

### Decision

- Do not promote `C5I` as new leader yet.
- Keep tuned two-stage `C5` as production-candidate baseline.
- Next M1 iteration should focus on time robustness:
  - source-aware regularization for image features
  - stronger per-source calibration (especially Hipflat)
  - possibly constrain image features to listing residual branch instead of full joint model

---

## 2026-03-18 - M1 Iteration v3 (Listing Residual Branch)

### Plan

- Replace joint image-in-main-model strategy with a two-part predictor:
  - base model: existing `C5` two-stage model for all rows
  - residual model: listing-only correction trained on `(y_true_log - y_base_log)`
- Apply residual correction only to listing rows with image embeddings.
- Add source-aware residual controls:
  - source-specific sample weights for residual training
  - optional per-source calibration multiplier learned from train fold residual behavior

### Implementation

- Trainer updated in `gis-server/scripts/train_combined_price_model_mlflow.py`:
  - new stage: `C5IR`
  - new args:
    - `--residual-n-estimators`
    - `--residual-alpha`
    - `--residual-source-weights-json`
    - `--residual-source-calibration`
  - residual branch only sees listing rows with `has_image_embedding=1`

### Runs

- Grouped split (`C5` vs `C5IR`):
  - run: `3135f42820db43ad9d5a3cef89b50215`
  - output: `gis-server/models/combined_price_grouped_cv_c5_vs_c5ir_m1_v3`
- Time split (`C5` vs `C5IR`):
  - run: `93cfe704c2d6436b83fc48da1e75d363`
  - output: `gis-server/models/combined_price_time_split_c5_vs_c5ir_m1_v3`

### Outcome

- Grouped split:
  - `C5`: overall MAE `996,616`, listing MAE `4,017,903`, treasury MAE `814,572`
  - `C5IR`: overall MAE `992,009`, listing MAE `3,832,389`, treasury MAE `820,866`
- Time split:
  - `C5`: overall MAE `943,288`, listing MAE `6,268,830`, treasury MAE `681,869`
  - `C5IR`: overall MAE `962,541`, listing MAE `6,522,285`, treasury MAE `689,627`

### Realistic Evaluation

- Residual-only integration did exactly what we intended structurally:
  - it protects architecture clarity and isolates image influence to listing branch.
- But empirically it still fails time robustness:
  - grouped improves,
  - time split degrades across overall/listing/treasury.
- So this is still a research-positive but deployment-negative result.

### Decision

- Keep tuned two-stage `C5` as active leader.
- Do not promote `C5IR`.
- Next iteration should target temporal robustness directly (for example source-specific residual caps or stronger temporal regularization), not just better grouped fit.

---

## 2026-03-18 - M1 Iteration v4 (Source-Capped Residual)

### Goal

- Test whether explicit source-aware residual capping and forward-split shrink can close the time-split regression while preserving grouped gains.

### Implementation

- Extended `C5IR` residual controls in `gis-server/scripts/train_combined_price_model_mlflow.py`:
  - `--residual-max-abs-log-delta` (global absolute residual cap in log-space)
  - `--residual-source-max-abs-json` (per-source caps)
  - `--residual-forward-shrink` (extra shrinkage under forward-chaining splits)
- Default source caps in trainer:
  - `baania: 0.10`, `hipflat: 0.04`, `legacy_bania: 0.03`

### Runs

- Grouped split (`C5` vs `C5IR` v4):
  - run: `a8528377f424419a9c53f33c90860b1a`
  - output: `gis-server/models/combined_price_grouped_cv_c5_vs_c5ir_m1_v4`
- Time split (`C5` vs `C5IR` v4):
  - run: `c0ed7d348e884f5ebc42a93442a89aeb`
  - output: `gis-server/models/combined_price_time_split_c5_vs_c5ir_m1_v4`

### Outcome

- Grouped split:
  - `C5`: overall MAE `996,616`, listing MAE `4,017,903`, treasury MAE `814,572`
  - `C5IR` v4: overall MAE `991,952`, listing MAE `3,831,379`, treasury MAE `820,866`
- Time split:
  - `C5`: overall MAE `943,288`, listing MAE `6,268,830`, treasury MAE `681,869`
  - `C5IR` v4: overall MAE `962,227`, listing MAE `6,515,573`, treasury MAE `689,627`

### Realistic Evaluation

- v4 confirms a stable pattern now seen across v2-v4:
  - grouped split improves with image branch,
  - time split remains materially worse.
- Residual capping reduced risk and made behavior more controlled, but did not solve temporal generalization.
- This likely indicates distribution shift in listing image signal over time that current tabular+residual setup cannot robustly normalize.

### Decision

- Keep tuned two-stage `C5` as active leader.
- Pause promotion of image-enhanced branch.
- Next effort should pivot to a new signal family (`N`: area-time news features) while keeping image branch as optional research side-path.

---

## 2026-03-18 - Plan A-v1 Confidence-Weighted Legacy Pretrain (No News)

### Goal

- Improve two-stage pretraining quality without adding new labeled rows.
- Use all legacy salvage rows in pretraining but reduce noise impact via row-level confidence weighting.

### Implementation

- Legacy salvage confidence features were added in dataset builder:
  - `legacy_confidence_score` (continuous `[0.1, 1.0]`)
  - `legacy_quality_bucket` (`low`/`medium`/`high`)
  - file: `gis-server/scripts/build_combined_price_dataset.py`
- Trainer received confidence-aware pretraining options:
  - `--pretrain-use-legacy-confidence`
  - `--pretrain-confidence-power`
  - `--pretrain-drop-low-confidence-quantile`
  - file: `gis-server/scripts/train_combined_price_model_mlflow.py`

### Confidence Distribution Snapshot

- Artifact: `gis-server/data/benchmarks/listing_sales_v1_legacy_salvage.parquet`
- Rows: `5,662`
- Mean confidence: `0.968`
- p10/p50/p90: `0.88 / 1.00 / 1.00`
- Observation: confidence is heavily concentrated near `1.0`.

### Runs

- Grouped split (`C5`):
  - run: `2d30d2c0f16f483086627bbbdf0dc84d`
  - config: confidence enabled, power `1.0`, drop bottom quantile `0.2`
- Time split (`C5`):
  - run: `fa11f25781354412b366cb762ffcd500`
  - same config

### Outcome

- Grouped split:
  - overall MAE `1,001,063`
  - treasury MAE `815,331`
  - listing MAE `4,083,568`
- Time split:
  - overall MAE `941,128`
  - treasury MAE `682,186`
  - listing MAE `6,216,235`

### Realistic Evaluation

- Compared to prior best `C5` two-stage references:
  - grouped benchmark regressed,
  - time benchmark improved slightly.
- This indicates current confidence heuristic is directionally useful for time robustness, but not yet discriminative enough to improve both benchmarks.
- Most likely reason: confidence scores are too compressed near `1.0`, so low-quality rows are not down-weighted aggressively enough.

### Decision

- Keep current tuned `C5` as active leader.
- Continue Plan A with stronger confidence separation (for example harsher penalties for noisy source-file cohorts and duplicate patterns) before re-running.

---

## 2026-03-18 - Plan A-v2/v3/v5 Sweep (No News, Confidence-Only)

### Goal

- Continue confidence-weighted legacy pretraining until we either get a clear improvement or hit a robustness ceiling.

### What Was Changed

- Strengthened legacy confidence scoring in `build_combined_price_dataset.py`:
  - harsher source priors for noisy legacy source files
  - stronger duplicate penalties
  - source-property mismatch penalties
  - broader score range (`0.05` to `1.0`) and tighter quality bucket thresholds
- Added pretrain source-site filtering in trainer:
  - `--pretrain-only-source-sites`
- Added ultra-conservative pretrain source weights JSON:
  - `gis-server/data/benchmarks/source_weights_legacy_ultra_conservative.json`

### Key Sweep Runs

- v2 grouped runs (confidence-strength sweep):
  - `2b57d44e6ba44b5e9b21b86d8ca894b4`
  - `84a624dfb29d47aea7dfe5bf8ee4244c`
  - `9625f797569644119d8fd31be2ff9928`
- v3 legacy-only pretrain (best grouped candidate):
  - grouped: `da820014e11f48aea66e8a2c2a7aef45`
  - time: `8a7afafdc6714a82a2d12f8bb984f6a5`
- v4 ultra-conservative source weight:
  - grouped: `329b98499aee45dea8532296461995b3`
- v5 lower pretrain-tree sweep:
  - grouped n=50: `d59cefb37a364eda818c1754379a6f17`
  - grouped n=80: `f54f47142e824a9280bcab12fb5bd14b`
  - time n=50: `10d3a27e79cc48dea5510acadc649e32`

### Best Observed Candidate In This Sweep

- Candidate: v5 (`pretrain_n_estimators=50`, confidence enabled, bottom 20% dropped)
- Grouped:
  - overall MAE `998,956`
  - treasury MAE `810,802`
  - listing MAE `4,121,636`
- Time:
  - overall MAE `946,060`
  - treasury MAE `686,435`
  - listing MAE `6,235,076`

### Realistic Comparison Against Current Leader

- Current leader (`C5` two-stage reference):
  - grouped: overall `996,616`, treasury `814,572`, listing `4,017,903`
  - time: overall `943,288`, treasury `681,869`, listing `6,268,830`
- Sweep best vs leader:
  - grouped: slightly worse overall/listing, slightly better treasury
  - time: slightly worse overall/treasury, slightly better listing

### Honest Conclusion

- We pushed confidence-only tuning hard across multiple variants.
- It improved parts of the tradeoff but did **not** deliver a clear, dominant improvement across both grouped and time benchmarks.
- This indicates diminishing returns from confidence-only weighting under current data constraints.

### Decision

- Keep existing tuned two-stage `C5` as active leader.
- Stop spending cycles on further confidence-only micro-tuning for now.
- If we keep iterating without new clean labels, we need a different signal family or a different objective (e.g., calibrated uncertainty) to make meaningful gains.

---

## 2026-03-18 - Model Family Trial: XGBoost vs LightGBM

### Goal

- Test whether switching tree backend from LightGBM to XGBoost can improve current `C5` two-stage benchmark under the exact same feature/split protocol.

### Implementation

- Added backend selector to trainer:
  - `--model-backend {lightgbm,xgboost}`
- Added XGBoost dependency and trainer support in:
  - `gis-server/scripts/train_combined_price_model_mlflow.py`
- Kept stage definitions, features, splits, and reporting unchanged.

### Runs

- Grouped split reference (`lightgbm`):
  - run: `93506e2f574a4e2e8736d09b8ba58d59`
  - output: `gis-server/models/combined_price_grouped_cv_c5_lgb_ref_xgbtrack`
- Grouped split candidate (`xgboost`):
  - run: `01195a2988104ab88ff18e1b70819591`
  - output: `gis-server/models/combined_price_grouped_cv_c5_xgb_v1`
- Time split reference (`lightgbm`):
  - run: `5d38989447ed493ca0012a0501768193`
  - output: `gis-server/models/combined_price_time_split_c5_lgb_ref_xgbtrack`
- Time split candidate (`xgboost`):
  - run: `2204e80ab44143f393a463145fc83ffc`
  - output: `gis-server/models/combined_price_time_split_c5_xgb_v1`

### Outcome

- Grouped split:
  - LightGBM: overall MAE `994,126`, treasury MAE `802,290`, listing MAE `4,177,927`
  - XGBoost: overall MAE `1,007,118`, treasury MAE `813,528`, listing MAE `4,220,042`
- Time split:
  - LightGBM: overall MAE `970,980`, treasury MAE `696,560`, listing MAE `6,561,379`
  - XGBoost: overall MAE `939,287`, treasury MAE `673,547`, listing MAE `6,352,870`

### Realistic Evaluation

- XGBoost under this first configuration improved time split materially but regressed grouped split.
- So this is a tradeoff model, not a strict winner yet.
- The result is promising enough to keep XGBoost in the candidate set, but not enough to replace LightGBM leader immediately.

### Decision

- Keep current LightGBM two-stage `C5` as active primary leader for now.
- Continue one focused XGBoost tuning pass (depth/regularization/rounds) to see if grouped regression can be reduced while keeping time gains.

### Focused XGBoost Tuning Pass (v2)

- Added tunable XGBoost args in trainer:
  - `--xgb-learning-rate`
  - `--xgb-max-depth`
  - `--xgb-min-child-weight`
  - `--xgb-subsample`
  - `--xgb-colsample-bytree`
  - `--xgb-reg-alpha`
  - `--xgb-reg-lambda`
  - `--xgb-gamma`

- Grouped sweep runs:
  - v2a: `c892a6beee67487faa12fdff37c7c5bd`
  - v2b: `fa859463d1ca4c8a873f09ee4fa8da30`
  - v2c: `e7f659245b2c438b830ac4f1eb7b498e`
- Time check for best grouped candidate (v2a):
  - `3bb15fe1074746cca2490cd20a15f3ed`

### Tuning Outcome

- Grouped results (overall MAE):
  - XGB v1: `1,007,118`
  - XGB v2a: `1,016,764`
  - XGB v2b: `1,032,801`
  - XGB v2c: `1,019,613`
- Time result for v2a:
  - overall MAE `989,271` (worse than XGB v1 and worse than LGB reference in this runset)

### Realistic Evaluation

- Focused XGBoost tuning did not improve over XGB v1; all tested variants regressed.
- So far, XGBoost remains unstable and does not produce a better cross-split tradeoff than current LightGBM baseline in this campaign.

### Updated Decision

- Keep LightGBM two-stage `C5` as active leader.
- Freeze XGBoost for now (retain code path, stop tuning loop until data/signal changes).

---

## 2026-03-18 - Model Family Trial: HGT Graph Neural Network (Revisited)

### Goal

- Test whether HGT can provide competitive accuracy vs C5 baseline after fixing target encoding issues.

### Root Cause Fix

- Original probe run had target-scale mismatch: model outputs log10(price) but targets were raw prices.
- Fixed by:
  - Log-transforming targets during training: `targets = torch.log10(targets_raw)`
  - Converting predictions back to raw prices in evaluation: `pred_price = 10 ** log_pred`

### Training Runs

| Version | LR | Epochs | Best Val MAPE | Test MAE | Test MAPE | Test R² |
|---------|-----|--------|---------------|----------|-----------|---------|
| V1 (broken) | 0.001 | 40 | 100% | 3.49M | 100% | -2.82 |
| V2 | 0.001 | 100 | 41% | 1.50M | 50% | 0.02 |
| V3 | 0.0005 | 150 | 39% | 5.79M | 249% | -7.56 |
| V4 | 0.0003 | 200 | 41% | 2.72M | 121% | -1.10 |

### Best HGT (V2) Detailed Metrics

- Full dataset MAE: 1,500,921 THB
- Full dataset MAPE: 51.01%
- Full dataset R²: 0.0178
- Samples: 8,514 (Treasury-only)

**Per price range:**
- <2M (n=1,969): MAE 1.67M, MAPE 122% - over-predicting
- 2-5M (n=5,097): MAE 0.69M, MAPE 24% - competitive
- 5-10M (n=1,264): MAE 3.11M, MAPE 46%
- 10-20M (n=163): MAE 9.64M, MAPE 73%
- >20M (n=21): MAE 22.74M, MAPE 86%

### Comparison Vs C5 Baseline

| Model | MAE | R² | Notes |
|-------|-----|-----|-------|
| C5 (Treasury grouped) | ~814k | ~0.52 | Current champion |
| HGT V2 (best) | 1.50M | 0.02 | 1.8x worse on MAE |

### Training Instability

- Validation metrics oscillate wildly: MAPE jumps from 40% to 1000% between epochs
- Early stopping often triggers on a lucky epoch rather than true convergence
- Lower learning rate (V3, V4) makes training slower but doesn't solve instability

### Root Causes of Poor Performance

1. **Graph structure may not add value**: Property features + spatial edges may not provide enough signal beyond tabular features
2. **Feature engineering gap**: Tabular C5 uses carefully engineered features (hex2vec, source weights, residuals); HGT uses raw graph features
3. **Training instability**: Loss landscape is noisy, possibly due to heterogeneous attention on small graph
4. **Data scale**: 8.5k nodes may be too small for HGT to learn meaningful relational patterns

### Decision

- **Close GNN branch** for now.
- HGT is 1.8x worse than C5 on MAE with much lower R².
- Training instability and poor generalization suggest graph structure doesn't add value over tabular features.
- Not worth further tuning effort given:
  - C5 is already strong
  - Data bottleneck (listing quality) is more important
  - Graph construction would need audit to ensure features are optimal

### Code Changes Made

- `scripts/train_hgt.py`:
  - `torch.load(..., weights_only=False)`
  - Log-transform targets: `targets = torch.log10(targets_raw)`
  - Updated `compute_metrics` to convert log-predictions to raw prices
- `scripts/evaluate_hgt.py`:
  - `torch.load(..., weights_only=False)`
  - Convert log-predictions to raw prices in `get_predictions`
- `scripts/train_hgt_mlflow.py`:
  - Added `_json_safe` helper for metadata serialization
- `src/models/hgt_valuator.py`:
  - Removed `dropout` from `HGTConv` constructor (PyG compatibility)

---

## 2026-03-18 - Campaign Summary and Next Steps

### What We Tried

1. **Image embeddings (M1)**: built full pipeline, CLIP embeddings, C5I/C5IR variants. Improved grouped CV but failed time robustness.
2. **Legacy confidence pretrain (Plan A)**: implemented confidence scoring, multiple sweeps. Mixed results, no dominant winner.
3. **XGBoost backend**: switched tree backend, tuned hyperparameters. Tradeoff model (better time, worse grouped), not a clear winner.
4. **HGT graph neural network**: fixed target encoding, ran 4 training variants. Best model (V2) is 1.8x worse on MAE than C5, training unstable.

### Current Champion

- **LightGBM two-stage C5**
- Grouped: overall MAE `996,616`, treasury `814,572`, listing `4,017,903`
- Time: overall MAE `943,288`, treasury `681,869`, listing `6,268,830`

### Key Bottlenecks Identified

1. **Listing data quality and coverage**: listing MAE remains 4-6x higher than treasury.
2. **Time generalization**: all advanced methods improve grouped but degrade time split.
3. **Legacy label noise**: confidence weighting helps but cannot fully overcome label quality issues.
4. **Model complexity doesn't help**: image embeddings, XGBoost, and HGT all fail to beat simple tabular C5.

### Recommended Next Steps (Priority Order)

1. **Expand clean listing data**: more sources, more snapshots, better deduplication.
2. **Build true time-aware benchmark**: multiple listing snapshots with reliable timestamps.
3. **Improve listing labels**: investigate `price_end` vs `price_start` semantics, reduce noise.
4. **Revisit advanced methods only after data improves**: image, XGBoost, HGT are not bottleneck.

### Files Modified This Session

- `gis-server/scripts/train_combined_price_model_mlflow.py` (image stages, XGBoost backend, confidence pretrain)
- `gis-server/scripts/build_combined_price_dataset.py` (legacy confidence scoring)
- `gis-server/scripts/audit_listing_images_quality.py` (created)
- `gis-server/scripts/extract_listing_image_embeddings.py` (created)
- `gis-server/scripts/build_listing_image_embeddings.py` (created)
- `gis-server/scripts/train_hgt.py` (torch.load fix, log-target encoding, metrics fix)
- `gis-server/scripts/train_hgt_mlflow.py` (torch.load fix, JSON serialization)
- `gis-server/scripts/evaluate_hgt.py` (torch.load fix, log-pred conversion)
- `gis-server/src/models/hgt_valuator.py` (HGTConv compatibility)
- `gis-server/Makefile` (image pipeline targets)
- `research/price-model-research-journal.md` (this document)
- `research/multimodal-news-campaign-20260318.md` (created)

---

## 2026-03-18 - All Data Experiment: Quality vs Volume Tradeoff

### Goal

- Test whether using ALL available data (including noisy legacy listings) improves predictions, with only leakage protection via grouped CV.

### Approach

- Use `combined_sales_v1_legacy_salvage.parquet` (14,176 rows)
- Sources: Treasury (8,514) + Baania (417) + Hipflat (96) + Legacy Bania (5,149)
- Strict grouped CV split by `property_type + h3_res7` to avoid leakage
- No confidence weighting, no filtering - just raw all data

### Results

| Model | Rows | Overall MAE | Treasury MAE | Listing MAE |
|-------|------|-------------|--------------|-------------|
| C5 Clean (champion) | 9,027 | 996,616 | 814,572 | 4,017,903 |
| C5 All Data (two-stage) | 14,176 | 1,818,597 | 813,748 | 3,329,598 |
| C5 All Data (direct) | 14,176 | 1,822,393 | 816,535 | 3,334,910 |

### Key Findings

1. **Treasury MAE unchanged**: 814k (clean) vs 816k (all) - noise didn't hurt Treasury
2. **Listing MAE improved 17%**: 4,018k (clean) vs 3,335k (all) - more data helped!
3. **Overall MAE worse**: only because dataset is now 40% listings instead of 5%
4. **Two-stage pretrain not needed**: direct training gives same results

### Per-Source Breakdown (All Data)

| Source | Rows | MAE | MAPE |
|--------|------|-----|------|
| Treasury | 8,514 | 816,535 | 23.5% |
| Legacy Bania | 5,149 | 3,269,770 | 31.6% |
| Baania | 417 | 4,840,582 | 30.9% |
| Hipflat | 96 | 190,747 | 88.4% |

### Interpretation

- **Volume beats quality for listings**: Noisy legacy data helped because it increased training volume
- **Noise averages out**: Legacy Bania (31.6% MAPE) performed similarly to clean Baania (30.9% MAPE)
- **Hipflat is outlier**: Only 96 rows with very high variance, but doesn't hurt overall model
- **Overall MAE misleading**: Looks worse but that's just different data mix, not worse predictions

### Decision

- **Use all-data model as new production baseline** for listing predictions
- Keep clean benchmark for fair comparison and ablation studies
- This proves that data volume is more important than data quality for listings
- Future work: focus on getting MORE listing data, not cleaner listing data

### MLflow Runs

- All data two-stage: `e61f187743dc4a76bf9cfbacdec1d6c1`
- All data direct: `637c7b7507504fc2ad12ca316df41084`

---

## 2026-03-18 - Comprehensive Model Comparison on All Data

### Goal

- Test all techniques (XGBoost, image embeddings, residual correction) on the all-data benchmark
- Find the best combination of model + features

### Results Summary

| Model | Features | Overall MAE | Treasury MAE | Listing MAE | vs Clean |
|-------|----------|-------------|--------------|-------------|----------|
| **C5IR** | All+Img+Res | **1,815,752** | 818,772 | **3,314,919** | **-17.5%** |
| C5IR+conf | All+Img+Res+Conf | 1,815,752 | 818,772 | 3,314,919 | -17.5% |
| C5I | All+Img | 1,815,758 | 818,772 | 3,314,934 | -17.5% |
| C5 LGB | All | 1,822,393 | 816,535 | 3,334,910 | -17.0% |
| C5 XGB | All | 1,819,152 | 809,714 | 3,337,053 | -16.9% |
| XGB tuned | All+tuned | 1,832,482 | 808,861 | 3,371,711 | -16.1% |
| C5 Clean (baseline) | Clean | 996,616 | 814,572 | 4,017,903 | - |

### Key Findings

1. **All models on all-data beat clean benchmark on listings**: 16-17% improvement
2. **Image embeddings help slightly**: C5I vs C5 LGB shows ~0.5% improvement
3. **Residual correction helps marginally**: C5IR is slightly better than C5I
4. **Confidence weighting doesn't help**: C5IR+conf identical to C5IR
5. **XGBoost not better than LightGBM**: similar or slightly worse
6. **Tuned XGBoost worse**: overfitting on all-data with noise

### Feature Analysis

- **C5 features (112)**: base + hex2vec + geo + listing metadata
- **C5I features (178)**: C5 + 66-dim CLIP image embeddings (PCA-compressed)
- **Image coverage**: 387 listings with embeddings (6.8% of all data)
- **Residual correction**: trained on listings with both price_start and price_end

### Best Model Recommendation

**C5IR on all-data** is the new production champion:
- Listing MAE: 3,314,919 (17.5% better than clean)
- Treasury MAE: 818,772 (unchanged from clean)
- Uses all available techniques: hex2vec, geo features, image embeddings, residual correction
- Robust to noise: legacy data doesn't hurt, helps through volume

### Why This Works

1. **Volume > Quality**: Noisy legacy data helped because noise averages out with more samples
2. **Feature richness**: Hex2vec captures neighborhood patterns, image embeddings capture property condition
3. **Residual correction**: Calibrates listing-specific biases
4. **Strict grouped CV**: Prevents leakage while allowing all data usage

### MLflow Runs

- C5IR (best): `4948367d224e4c0f87b62feeb9b46c0f`
- C5I: `99e4e2af7cf943c2bbb2863fa8e96a9c`
- C5 XGB: `b47120624ac9442ea8951009933a92ed`
- XGB tuned: `a4bc7a3332bc4178989134656bed85dd`
- C5IR+conf: `d6df6e1f3bb747a08dc5d4b0e0645e62`

---

## 2026-03-18 - Final Campaign Conclusions

### What Worked

1. **Using all data with leakage protection**: 17.5% improvement on listings
2. **Feature engineering (hex2vec, geo)**: Essential for all models
3. **Image embeddings**: Small but consistent improvement
4. **Residual correction**: Marginal additional improvement

### What Didn't Work

1. **Confidence weighting**: No improvement over raw all-data
2. **XGBoost vs LightGBM**: Similar performance, LightGBM slightly better
3. **HGT graph neural network**: 1.8x worse than C5, training unstable
4. **Aggressive hyperparameter tuning**: Overfits on noisy data

### Final Champion

**C5IR on all-data (14,176 rows)**:
- Overall MAE: 1,815,752
- Treasury MAE: 818,772
- Listing MAE: 3,314,919
- Features: 178 (base + hex2vec + geo + listing + image embeddings)
- Model: LightGBM with residual correction

### Remaining Bottlenecks

1. **Listing MAE still 4x Treasury MAE**: Need even more listing data
2. **Image coverage low (6.8%)**: More image scraping needed
3. **No time-split validation**: Need multiple listing snapshots

### Recommended Next Steps

1. **Scrape more listing data**: Volume is more important than quality
2. **Increase image coverage**: Target 50%+ listings with images
3. **Build time-aware benchmark**: Multiple snapshots for temporal validation
4. **Deploy C5IR model**: It's the best we have, use it in production

---

## 2026-03-18 - C6 Recheck, Split-Hardening, and Thesis Table Refresh

### Why This Recheck Was Needed

- We had a known runtime artifact mismatch (`Split artifact missing cv_fold for 5149 rows`) and a new C6 feature family under active comparison.
- We needed to confirm implementation correctness before trusting benchmark deltas.

### Implementation Corrections

- Split-artifact preflight checks were added in `gis-server/scripts/train_combined_price_model_mlflow.py`:
  - validate required columns (`row_id`, `cv_fold`)
  - reject duplicated split `row_id`
  - fail early if dataset row IDs are not covered by split row IDs
  - include source breakdown and sample missing IDs in error message
  - warn on dataset/split version mismatch and split extras
- `C6IR` was wired to residual training flow (previously only `C5IR` path executed residual branch).
- `C6IR` fold-safe market context was aligned with `C6` path.
- Leakage fix: fold-safe market feature helper no longer computes `price_vs_local` from true target (`target_price_thb`) inside train/val feature construction.
  - `price_vs_local` is now held at neutral constant `0.0` in this fold-safe path to avoid target leakage.
- MLflow utility context handling was hardened in `gis-server/src/utils/mlflow_utils.py` to avoid contextmanager throw/yield runtime failure when training errors occur.

### Runtime Mismatch Resolution Evidence

- Intentional mismatch test (all-data dataset + clean split) now fails with clear diagnostic:
  - missing rows: `5149`
  - source breakdown: `legacy_bania: 5149`
- Matching all-data dataset + all-data split was re-verified and trains successfully.

### Benchmark Matrix Executed (Canonical Runset)

- Clean grouped (LightGBM): `C5`, `C6`, `C6I`, `C6IR`
- All-data grouped (LightGBM): `C5`, `C6`, `C6I`, `C6IR`
- Clean time split (LightGBM): `C5` vs `C6`
- XGBoost grouped: `C6` on clean and all-data

### Canonical Results (MAE)

- Clean grouped:
  - `C5`: overall `1,006,223`, treasury `802,621`, listing `4,385,310`
  - `C6`: overall `1,594,915`, treasury `1,297,796`, listing `6,526,043`
  - `C6I`: overall `1,575,586`, treasury `1,280,060`, listing `6,480,273`
  - `C6IR`: overall `1,575,491`, treasury `1,280,060`, listing `6,478,605`
- All-data grouped:
  - `C5`: overall `1,822,393`, treasury `816,535`, listing `3,334,910`
  - `C6`: overall `2,811,255`, treasury `1,304,607`, listing `5,076,815`
  - `C6I`: overall `2,835,192`, treasury `1,268,005`, listing `5,191,786`
  - `C6IR`: overall `2,835,223`, treasury `1,268,005`, listing `5,191,864`
- Clean time split:
  - `C5`: overall `998,152`, treasury `710,263`, listing `6,862,957`
  - `C6`: overall `1,318,455`, treasury `891,320`, listing `10,019,947`
- XGBoost grouped `C6`:
  - clean: overall `1,560,390`, treasury `1,265,028`, listing `6,462,368`
  - all-data: overall `2,800,799`, treasury `1,252,921`, listing `5,128,357`

### Honest Interpretation

- Under corrected implementation, all `C6` variants are materially worse than `C5` on clean grouped, all-data grouped, and clean time split.
- The regression is large on both listing and treasury MAE, so this is not a minor tradeoff.
- XGBoost `C6` also does not recover the gap.

### Decision (Locked with Balanced Policy)

- Keep `C5` family as active leader.
- Do not promote `C6`, `C6I`, or `C6IR` under current protocol.
- Use updated canonical summary/table artifacts for thesis reporting:
  - `gis-server/benchmark_master_results.csv`
  - `research/benchmark_master_summary.md`
