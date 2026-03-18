# Comprehensive Model Benchmark Summary

## Scope and Protocol

- Benchmarks in this report are generated from canonical `metrics_*.json` artifacts, not from ad-hoc notes.
- Primary selection policy is **balanced listing improvement + treasury stability**.
- Acceptance defaults (locked):
  - listing MAE improvement target: `>= 3%` vs `C5` baseline on both clean and all-data grouped benchmarks.
  - treasury MAE regression cap: `<= 2%` on clean grouped and `<= 3%` on all-data grouped.

## Canonical Results Table

| Dataset | Model | Stage | Overall MAE | Treasury MAE | Listing MAE | Overall R2 | Listing delta vs C5 | Treasury delta vs C5 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| clean_grouped | LightGBM | C5 | 1,006,223 | 802,621 | 4,385,310 | 0.779 | 0.00% | 0.00% |
| clean_grouped | LightGBM | C6 | 1,594,915 | 1,297,796 | 6,526,043 | 0.454 | +48.82% | +61.70% |
| clean_grouped | LightGBM | C6I | 1,575,586 | 1,280,060 | 6,480,273 | 0.469 | +47.78% | +59.48% |
| clean_grouped | LightGBM | C6IR | 1,575,491 | 1,280,060 | 6,478,605 | 0.469 | +47.74% | +59.48% |
| all_grouped | LightGBM | C5 | 1,822,393 | 816,535 | 3,334,910 | 0.819 | 0.00% | 0.00% |
| all_grouped | LightGBM | C6 | 2,811,255 | 1,304,607 | 5,076,815 | 0.564 | +52.23% | +59.77% |
| all_grouped | LightGBM | C6I | 2,835,192 | 1,268,005 | 5,191,786 | 0.571 | +55.67% | +55.29% |
| all_grouped | LightGBM | C6IR | 2,835,223 | 1,268,005 | 5,191,864 | 0.571 | +55.68% | +55.29% |
| clean_time | LightGBM | C5 | 998,152 | 710,263 | 6,862,957 | 0.784 | 0.00% | 0.00% |
| clean_time | LightGBM | C6 | 1,318,455 | 891,320 | 10,019,947 | 0.617 | +46.00% | +25.50% |
| clean_grouped | XGBoost | C6 | 1,560,390 | 1,265,028 | 6,462,368 | 0.475 | n/a | n/a |
| all_grouped | XGBoost | C6 | 2,800,799 | 1,252,921 | 5,128,357 | 0.573 | n/a | n/a |

## Time-Split C5 vs C6 Check

| Dataset | Model | Stage | Overall MAE | Treasury MAE | Listing MAE |
|---|---|---|---:|---:|---:|
| clean_time | LightGBM | C5 | 998,152 | 710,263 | 6,862,957 |
| clean_time | LightGBM | C6 | 1,318,455 | 891,320 | 10,019,947 |

Interpretation:

- `C6` is materially worse than `C5` on the source-aware time split across overall, treasury, and listing MAE.

## Decision Against Acceptance Gates

- Clean grouped (`C6` family vs `C5`): listing MAE regresses by `+47%` to `+49%` and treasury MAE regresses by `+59%` to `+62%`.
- All-data grouped (`C6` family vs `C5`): listing MAE regresses by `+52%` to `+56%` and treasury MAE regresses by `+55%` to `+60%`.
- Conclusion: no `C6` variant passes the locked balanced acceptance policy.

## Feature Engineering Findings (Current Cycle)

- Distance, density, composition, accessibility, and market-context were re-validated in implementation and rerun under clean/all/time splits.
- Hex2Vec remains a valuable component in the stable tabular path (`C4/C5` lineage).
- Image branch (`I` and `IR`) still does not rescue the `C6` family under the current data/split protocol.
- HGT remains a negative finding (not competitive versus tabular baselines).

## Implementation Notes Added This Cycle

- Added split-artifact compatibility preflight with explicit diagnostics in `gis-server/scripts/train_combined_price_model_mlflow.py`.
- Added `C6IR` execution wiring to residual training path in `gis-server/scripts/train_combined_price_model_mlflow.py`.
- Added fold-safe market-context handling in residual CV path and removed label-leaking `price_vs_local` computation.
- Fixed MLflow context manager behavior in `gis-server/src/utils/mlflow_utils.py` to avoid contextmanager runtime failure on inner exceptions.

## Canonical Artifact Paths

- Master CSV: `gis-server/benchmark_master_results.csv`
- Clean grouped C5/C6/C6I/C6IR: `gis-server/models/benchmark_clean_lgb_c5_c6_c6i_c6ir_v2/stage_summary.json`, `gis-server/models/benchmark_clean_lgb_c6_c6i_v2/stage_summary.json`, `gis-server/models/benchmark_clean_lgb_c6ir_v2/stage_summary.json`
- All grouped C5/C6/C6I/C6IR: `gis-server/models/benchmark_all_lgb_c5_c6_c6i_c6ir/stage_summary.json`, `gis-server/models/benchmark_all_lgb_c6_c6i_v2/stage_summary.json`, `gis-server/models/benchmark_all_lgb_c6ir_v2/stage_summary.json`
- Clean time C5/C6: `gis-server/models/benchmark_clean_lgb_time_c5/stage_summary.json`, `gis-server/models/benchmark_clean_lgb_time_c6_v2/stage_summary.json`
- XGBoost C6 clean/all grouped: `gis-server/models/benchmark_clean_xgb_c6_v2/stage_summary.json`, `gis-server/models/benchmark_all_xgb_c6_v2/stage_summary.json`
