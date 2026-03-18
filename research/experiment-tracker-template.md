# Experiment Tracker Template

Use this document as the canonical tracker for benchmark, multimodal, and HGT experiments.

---

## 1. Tracker Rules

- Every experiment gets a unique run ID
- Every experiment must reference a fixed data snapshot or dataset version
- Every experiment must declare split strategy explicitly
- Every experiment must report overall and source-level results
- No experiment should be considered valid without leakage notes

---

## 2. Benchmark Success Gates

### Project-Level Success
- `10%` improvement in `MAE`
- `+5pp` improvement in `% within 10%`

### Practical Acceptance
- listing-side metrics improve materially
- Treasury-side degradation remains small and acceptable
- gains hold on the primary time-based benchmark

### Treasury Tolerance
- target tolerance: Treasury MAE degradation `< 2-3%`

---

## 3. Experiment Metadata Template

Copy this block for every run.

```md
## Run: <RUN_ID>

- Date:
- Owner:
- Stage: `C0/C1/C2/C3/C4/C5/M1/M2/M3/M4/G1/G2/G3`
- Objective:
- Status: `planned / running / completed / invalidated`
- Code version / git SHA:
- Dataset version:
- Benchmark split:
- Model family:
- Model configuration summary:
- Notes:
```

---

## 4. Required Run Fields

For each run, capture the following.

### Data Definition
- sources included
- sale-only confirmation
- exact-price-only or range-included
- property types included
- geography included
- row count total
- row count by source
- row count with images
- row count without images

### Split Definition
- primary split type
- secondary split type if any
- time window
- grouping keys
- duplicate handling rule

### Feature Definition
- target definition
- core structured features
- geo features
- `hex2vec` included or not
- text features included or not
- image embeddings included or not
- image metadata included or not
- source markers included or not
- missingness flags included or not

### Modeling Definition
- algorithm
- objective/loss
- important hyperparameters
- calibration or residual modeling used or not

---

## 5. Required Metrics Table

Use this table for every completed run.

| Metric Slice | MAE | % within 10% | MAPE | RMSE | R2 | Notes |
|---|---:|---:|---:|---:|---:|---|
| Overall |  |  |  |  |  |  |
| Treasury |  |  |  |  |  |  |
| Listing |  |  |  |  |  |  |
| Source: Baania |  |  |  |  |  |  |
| Source: Hipflat |  |  |  |  |  |  |
| Source: Private/Appraisal |  |  |  |  |  |  |
| Has images |  |  |  |  |  |  |
| No images |  |  |  |  |  |  |
| Property type A |  |  |  |  |  |  |
| Property type B |  |  |  |  |  |  |

Add/remove slices depending on actual data coverage.

---

## 6. Benchmark Comparison Table

Use this table to compare important runs.

| Run ID | Stage | Split | Features | Overall MAE | Overall %<10 | Treasury MAE | Listing MAE | Listing %<10 | Treasury delta | Listing delta | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| C0 | Treasury baseline | spatial/time | structured+geo |  |  |  |  |  |  |  |  |
| C1 | combined common |  |  |  |  |  |  |  |  |  |  |
| C2 | source-aware |  |  |  |  |  |  |  |  |  |  |
| C3 | geo-enhanced |  |  |  |  |  |  |  |  |  |  |
| C4 | +hex2vec |  |  |  |  |  |  |  |  |  |  |
| C5 | +metadata/text-lite |  |  |  |  |  |  |  |  |  |  |
| M1 | +image embedding |  |  |  |  |  |  |  |  |  |  |
| M2 | +image metadata |  |  |  |  |  |  |  |  |  |  |
| G1 | HGT source-aware |  |  |  |  |  |  |  |  |  |  |

---

## 7. Run Review Template

```md
### Review: <RUN_ID>

- What changed from previous best:
- Expected effect:
- Actual effect:
- Did listing improve:
- Did Treasury degrade:
- Did results hold on primary split:
- Did results hold on secondary split:
- Leakage concerns:
- Recommendation: `keep / iterate / discard`
```

---

## 8. Failure Analysis Template

For promising or surprising runs, answer:

- biggest underpredictions
- biggest overpredictions
- source-specific failure patterns
- property-type-specific failure patterns
- high-price segment behavior
- no-image vs image-rich behavior
- suspicious duplicates or stale listings
- whether the model is regressing to source mean

---

## 9. Experiment Ladder

### Combined Tabular
- `C0` Treasury-only reproduction
- `C1` combined common features
- `C2` `C1 + source_type + source_site + missingness`
- `C3` `C2 + geo/H3/distance`
- `C4` `C3 + hex2vec`
- `C5` `C4 + listing metadata/text-lite`

### Multimodal
- `M1` best `C* + image embedding`
- `M2` `M1 + image metadata`
- `M3` image count sensitivity
- `M4` pooling variants

### HGT
- `G1` source-aware safe-split HGT
- `G2` richer node features
- `G3` optional image-aware graph

---

## 10. Decision Log

Use this section for final stage gates.

| Date | Decision | Based On | Approved Next Step |
|---|---|---|---|
| 2026-03-12 | Adopt `combined_sales_v1` as the current CPU benchmark dataset | `gis-server/data/benchmarks/combined_sales_v1.parquet` plus audit artifacts | Continue CPU tabular ladder and improve benchmark validity |
| 2026-03-12 | Keep `C5` as the best current CPU baseline | MLflow run `62390f07bdab4b3eb1bbe14583f7ae41` and `gis-server/models/combined_price_cpu_mlflow/stage_summary.json` | Add grouped split and improve listing coverage before multimodal work |

---

## 12. Current Project Snapshot

### Run: CPU_PHASE_A_2026-03-12

- Date: 2026-03-12
- Owner: OpenCode
- Stage: `C1/C2/C3/C4/C5`
- Objective: establish the strongest CPU-feasible combined Treasury + listing tabular baseline
- Status: `completed`
- Code version / git SHA: `caf5d28bad8982ea80addc83df697611b4786e1a`
- Dataset version: `combined_sales_v1`
- Benchmark split: mixed grouped CV with Treasury quarter buckets and listing duplicate-group hashing
- Model family: LightGBM
- Model configuration summary: source-aware tabular ladder from common features through geo, `hex2vec`, and listing metadata
- Notes: useful for CPU iteration, but still not the final trustworthy benchmark because listing date coverage is a single scrape snapshot

| Run ID | Stage | Split | Features | Overall MAE | Overall %<10 | Treasury MAE | Listing MAE | Listing %<10 | Treasury delta | Listing delta | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| CPU_2026-03-12_C1 | C1 | grouped CV | common only | 1,113,933 | 32.65 | 873,129 | 6,030,504 | 20.62 | baseline | baseline | discard |
| CPU_2026-03-12_C2 | C2 | grouped CV | `C1 + source + missingness` | 981,810 | 36.27 | 753,435 | 5,644,616 | 23.26 | strong gain | strong gain | keep |
| CPU_2026-03-12_C3 | C3 | grouped CV | `C2 + geo/H3/distance` | 953,394 | 37.55 | 723,644 | 5,644,246 | 21.34 | gain | flat | iterate |
| CPU_2026-03-12_C4 | C4 | grouped CV | `C3 + hex2vec` | 878,587 | 42.02 | 632,690 | 5,899,134 | 17.51 | strong gain | worse | iterate |
| CPU_2026-03-12_C5 | C5 | grouped CV | `C4 + listing metadata/text-lite` | 861,629 | 42.55 | 629,918 | 5,592,526 | 23.98 | best | recovered | keep |

### Run: CPU_GROUPED_CV_2026-03-12

- Date: 2026-03-12
- Owner: OpenCode
- Stage: `C1/C2/C3/C4/C5`
- Objective: re-evaluate the combined ladder on a stricter grouped split before image and HGT phases
- Status: `completed`
- Code version / git SHA: `caf5d28bad8982ea80addc83df697611b4786e1a`
- Dataset version: `combined_sales_v1`
- Benchmark split: `grouped_cv_h3_res7_property_type`
- Model family: LightGBM
- Model configuration summary: same CPU ladder as Phase A, but with a stricter `property_type + h3_res7` grouped split artifact
- Notes: this is the current preferred benchmark because it is more leakage-resistant than the earlier fold assignment

| Run ID | Stage | Split | Features | Overall MAE | Overall %<10 | Treasury MAE | Listing MAE | Listing %<10 | Treasury delta | Listing delta | Decision |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| GROUPED_2026-03-12_C1 | C1 | strict grouped CV | common only | 1,321,326 | 20.69 | 1,082,301 | 6,201,550 | 19.90 | harder | harder | discard |
| GROUPED_2026-03-12_C2 | C2 | strict grouped CV | `C1 + source + missingness` | 1,175,631 | 24.22 | 958,216 | 5,614,645 | 19.66 | improved | improved | keep |
| GROUPED_2026-03-12_C3 | C3 | strict grouped CV | `C2 + geo/H3/distance` | 1,150,537 | 24.70 | 940,238 | 5,444,276 | 21.58 | improved | improved | keep |
| GROUPED_2026-03-12_C4 | C4 | strict grouped CV | `C3 + hex2vec` | 1,028,791 | 29.53 | 809,484 | 5,506,430 | 22.78 | strong gain | slight regression | iterate |
| GROUPED_2026-03-12_C5 | C5 | strict grouped CV | `C4 + listing metadata/text-lite` | 1,013,377 | 29.78 | 800,766 | 5,354,304 | 21.34 | best | best MAE | keep |

---

## 11. Minimal Example Entry

```md
## Run: C4_2026-03-12_a

- Date: 2026-03-12
- Owner: <name>
- Stage: `C4`
- Objective: test whether `hex2vec` improves source-aware combined baseline
- Status: `completed`
- Code version / git SHA: <sha>
- Dataset version: combined_sales_v1
- Benchmark split: primary time-based source-aware split
- Model family: LightGBM
- Model configuration summary: structured + geo + source markers + missingness + hex2vec
- Notes: first trustworthy combined benchmark with `hex2vec`

| Metric Slice | MAE | % within 10% | MAPE | RMSE | R2 | Notes |
|---|---:|---:|---:|---:|---:|---|
| Overall |  |  |  |  |  |  |
| Treasury |  |  |  |  |  |  |
| Listing |  |  |  |  |  |  |
```
