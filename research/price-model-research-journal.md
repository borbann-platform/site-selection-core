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
