# Combined Treasury + Listing Price Prediction Research Plan

## Status
- Draft: finalized research plan
- Scope: sale price prediction only
- Primary objective: improve listing-side price prediction while keeping combined-source performance strong
- Secondary objective: evaluate whether listing images materially improve a combined Treasury + listing benchmark
- Research posture: multimodal tabular first, HGT as a gated follow-up track

---

## 1. Problem Statement

We want to improve the price prediction model by moving from the current baseline toward a combined-source, source-aware benchmark that uses:

- Treasury property price data
- scraped listing data
- geospatial features
- `hex2vec` embeddings
- optional image embeddings from listing photos

The key challenge is that Treasury and listing data are not drawn from the same label distribution:

- Treasury prices behave more like appraised/reference values
- listing prices are asking prices and are noisier, more heterogeneous, and likely more sensitive to visual condition and marketing quality

Because of that, any combined benchmark must be explicitly source-aware.

---

## 2. Finalized Decisions

### Locked Scope
- Task: `sale price prediction`
- Benchmark universe: `combined Treasury + listing`
- First benchmark target: `log1p(price_thb)`
- Main business metrics:
  - `MAE`
  - `% within 10%`
- Initial model path:
  1. combined tabular baseline
  2. combined source-aware baseline
  3. `+ hex2vec`
  4. `+ image embeddings`
  5. HGT only if justified

### Success Criteria
- Minimum improvement to justify shipping:
  - `10%` improvement in `MAE`
  - `+5 percentage point` improvement in `% within 10%`
- In addition:
  - listing-side performance must improve materially
  - Treasury-side performance should not degrade more than ~`2-3%` MAE unless there is a compelling business reason

### Explicitly Out Of Scope For Phase 1
- rent prediction
- full end-to-end image fine-tuning
- HGT-first modeling
- midpoint conversion of price ranges by default
- using only random splits as the primary benchmark

---

## 3. Current Repo Context

### Existing Baseline
Current documented baseline is a Treasury-focused LightGBM pipeline with spatial features.

Relevant files:
- `gis-server/scripts/train_baseline.py`
- `gis-server/models/baseline/cv_metrics.json`
- `gis-server/models/baseline/all_models_comparison.json`

Observed documented metrics:
- LightGBM spatial CV MAPE around `16.8-17.4%`
- MAE around `595k-633k THB`

### Existing HGT Research
Current HGT / S2-HGT research already mixes source types conceptually, but documented listing performance is still weak.

Relevant files:
- `gis-server/docs/s2_hgt_progress.md`
- `gis-server/scripts/build_subset_graph.py`
- `gis-server/scripts/train_s2hgt.py`

Important note:
- HGT currently has source-awareness, but current research results do not yet beat the strong tabular baseline as a practical benchmark for this task.

### Existing Listing / Image Infrastructure
Listing and image storage structures already exist.

Relevant files:
- `gis-server/src/models/realestate.py`
- `gis-server/scripts/etl/load_scraped_projects.py`

Important note:
- image data exists in the platform
- image features are not yet used in baseline or current HGT training

---

## 4. Working Hypotheses

### H1
A combined-source benchmark can outperform single-source baselines if source differences are modeled explicitly.

### H2
`hex2vec` remains useful in the combined setup because it provides location context shared across Treasury and listings.

### H3
Listing images will improve combined benchmark performance mainly through better listing-side prediction, especially where visual quality and condition matter.

### H4
A multimodal tabular model (`LightGBM + structured + geo + image embeddings`) will likely be a stronger and cheaper first milestone than HGT.

### H5
HGT is only worth continuing if graph structure adds signal not already captured by:
- source indicators
- location features
- listing metadata
- image embeddings

---

## 5. Key Risks

### Label Risk
- Treasury and listing prices measure different things
- asking prices may be stale, inflated, or strategic

### Leakage Risk
- duplicate or reposted listings
- same property appearing multiple times across time
- possible overlap between Treasury and listing records
- image duplicates across listings

### Evaluation Risk
- current spatial split is not enough for listing dynamics
- time drift matters for asking prices

### Schema Risk
- Treasury rows have stronger structured fields
- listing rows may have richer metadata and images but noisier labels

### Image Risk
- many listing images may be low quality, duplicated, watermarked, or not informative
- image coverage may be biased toward premium segments

---

## 6. Benchmark Design

We will maintain one official benchmark, but every experiment must be reported in multiple views.

### Official Benchmark
Combined Treasury + listing sale-price prediction benchmark.

### Required Reporting Views
For every run, report:
- overall
- Treasury-only
- listing-only
- by source site
- by property type
- by image availability
- by geography if useful

### Primary Evaluation Split
Source-aware time-based split:
- Treasury split by `updated_date`
- listings split by `scraped_at` or the best available listing timestamp
- source-specific splits combined into a shared train/val/test benchmark

### Secondary Evaluation Split
Grouped spatial / duplicate-aware split:
- district or area group
- `source + source_listing_id`
- project/group identifier if available
- approximate duplicate fingerprint if needed

### Why Two Splits
- time split measures future generalization
- grouped spatial split measures robustness to neighborhood leakage and repost duplication

---

## 7. Unified Modeling Table

We should build one modeling table that aligns Treasury and listing rows while preserving source differences.

### Core Fields
- `row_id`
- `source_type`
- `source_site`
- `target_price_thb`
- `target_log_price`
- `event_date`
- `property_type`
- `area_sqm`
- `land_area`
- `floors`
- `building_age`
- `lat`
- `lon`
- `district`
- `subdistrict`
- `h3_index`
- `has_images`
- `image_count`

### Recommended Additional Fields
- missingness flags for major structured variables
- listing metadata fields if clean:
  - bedrooms
  - bathrooms
  - furnishing
  - facilities
  - developer
  - completion date
- text-derived features later if useful

### Source-Specific Mapping Principles
- Treasury:
  - reliable structured features
  - no images
- Listings:
  - noisier targets
  - richer metadata
  - images available
- keep source markers explicit; do not hide source mismatch

### Phase 1 Row Inclusion Rule
Use:
- sale rows only
- exact single-price listings only by default

Avoid initially:
- price ranges converted to midpoints
- unclear sale/rent records
- rows with invalid location or invalid target

---

## 8. Data Audit Checklist

Before training, produce a short audit report.

### Coverage
- total rows by source
- usable sale rows by source
- usable rows after exact-price filter
- valid coordinates coverage
- valid area coverage
- valid date coverage
- image coverage rate

### Distribution
- target distribution by source
- area distribution by source
- property type distribution by source
- district distribution by source

### Quality
- duplicate/repost rate
- cross-source overlap rate
- missingness by field
- proportion of range-priced listings
- suspected rent contamination in sale data

### Image Audit
- % with images
- average images per listing
- fetched vs unfetched coverage
- duplicate image rate
- low-quality / tiny image rate
- presence of floorplans, logos, contact cards, watermarks

---

## 9. Baseline Modeling Roadmap

## Phase A: Combined Tabular Baseline

### C0 - Treasury Baseline Reproduction
Goal:
- reproduce current Treasury-only baseline to verify environment and metrics

### C1 - Combined Common-Feature Baseline
Goal:
- train one model on Treasury + listings using only common aligned features

### C2 - Source-Aware Combined Baseline
Add:
- `source_type`
- `source_site`
- missingness flags

Goal:
- let the model learn systematic source shifts

### C3 - Geo-Enhanced Combined Baseline
Add:
- H3 features
- distance features
- existing geospatial context

### C4 - Combined `hex2vec` Baseline
Add:
- `hex2vec` embedding features

Goal:
- establish best non-image benchmark

### C5 - Metadata/Text-Lite Enhancement
Add only if clean enough:
- listing metadata fields
- light text features

Goal:
- test whether cheap listing-specific features already capture much of the missing signal

### Preferred Model Class
- start with `LightGBM`
- optionally compare `CatBoost` later if categorical handling becomes important

---

## 10. Multimodal Image Roadmap

Only start after the best combined non-image baseline is stable.

### M1 - Add Listing-Level Image Embeddings
- use pretrained encoder only
- no fine-tuning
- listing rows receive image embeddings
- Treasury rows receive zero vector + `has_images=0`

### M2 - Add Image Metadata
Possible additions:
- image count
- primary image available
- embedding variance
- basic image quality indicators

### M3 - Image Count Sensitivity
Compare:
- top-1
- top-3
- top-5

### M4 - Pooling Variants
Only if needed:
- mean pooling
- mean + max pooling
- lightweight attention pooling

### Recommended Initial Encoder
Use one only for the first pilot:
- `CLIP` or `DINOv2`

### Why Not Fine-Tune Initially
- cheaper
- faster
- easier to cache
- more compatible with low-budget Colab-style runs

---

## 11. HGT Research Track

HGT is explicitly a second-stage research path, not the first milestone.

### Entry Criteria
Only proceed if:
- best multimodal tabular model is stable
- listing-side gains remain insufficient
- there is a clear hypothesis that graph relations add information beyond flat features

### Most Promising Graph Entities
- property / listing
- source / source_type
- h3 cell
- POI anchor
- condo project
- optional image node later

### Recommended HGT Sequence
- G1: improved source-aware combined graph with better benchmark split
- G2: richer node features from combined structured data
- G3: optional image-derived nodes or edges later

### HGT Go/No-Go Rule
HGT must beat the best multimodal tabular model by a meaningful margin:
- roughly `2-3%` additional lift or better
- while staying maintainable

If not, HGT remains research-only.

---

## 12. Metrics Framework

### Primary Metrics
- `MAE`
- `% within 10%`

### Secondary Metrics
- `MAPE`
- `RMSE`
- `R²` on transformed target
- `% within 20%`

### Required Slices
- Treasury
- listing
- source site
- property type
- image vs no-image
- price band
- geography

### Acceptance Rules
A model is only considered better if:
- listing-side metrics improve materially
- Treasury degradation is small and understood
- improvement persists on the time-based benchmark

---

## 13. Experiment Matrix

### Baseline Ladder
- `C0` Treasury-only reproduction
- `C1` combined common features
- `C2` `C1 + source markers + missingness`
- `C3` `C2 + geo/H3/distance`
- `C4` `C3 + hex2vec`
- `C5` `C4 + listing metadata/text-lite`

### Multimodal Ladder
- `M1` best `C* + image embedding`
- `M2` `M1 + image metadata`
- `M3` top-1 vs top-3 vs top-5
- `M4` pooling variants if needed

### HGT Ladder
- `G1` combined source-aware HGT on safe split
- `G2` richer combined features
- `G3` optional image-aware graph

---

## 14. Required Deliverables

### Data
- unified modeling table spec
- source mapping notes
- audit report

### Benchmarking
- fixed evaluation protocol
- split generation rules
- leakage checklist

### Modeling
- baseline leaderboard
- multimodal leaderboard
- segment-level results
- failure case review

### Decision Artifact
- decision memo recommending one of:
  - keep combined tabular baseline
  - adopt multimodal combined model
  - continue HGT research
  - stop HGT research

---

## 15. Practical Resource Plan

### Budget Assumption
- current working budget: around `$50` or Google Colab

### Recommended Compute Strategy
- tabular baselines: CPU or standard Colab is enough
- image embedding pilot: single GPU, cached embeddings
- HGT: subset-first only

### Cost-Saving Principles
- extract embeddings once and cache them
- start with top `1-3` images per listing
- avoid vision fine-tuning in early phases
- avoid full HGT scaling before proving value on subset

---

## 16. Open Questions To Resolve During Execution

### Data Questions
- final usable count of sale listings after cleaning
- final date coverage by source
- exact availability of exact-price sale listings
- stability of `source_listing_id`
- cross-source duplicate rate

### Modeling Questions
- whether one global combined model is enough
- whether listing-side residual or calibration model is needed
- whether `log(price_per_sqm)` should be tested in parallel

### Image Questions
- actual fetched-image coverage
- image quality and duplicate rate
- whether primary image alone is already informative enough

---

## 17. Things We Explicitly Oppose

- HGT-first benchmark
- random split as the primary benchmark
- relying only on overall metrics
- midpoint price-range labels in phase 1 by default
- image pipeline before data audit
- judging success without source-level scorecards

---

## 18. Final Recommendation

The official plan is:

1. Build a combined Treasury + listing sale-price benchmark  
2. Make it source-aware and split-safe  
3. Establish the strongest non-image tabular baseline  
4. Add listing image embeddings in the cheapest robust way  
5. Only then evaluate whether HGT adds real value beyond the multimodal tabular model  

This gives the highest chance of producing a useful result under limited budget while still preserving an HGT research path.

---

## 19. Suggested File References

Useful repo references for future work:
- `gis-server/scripts/train_baseline.py`
- `gis-server/models/baseline/cv_metrics.json`
- `gis-server/models/baseline/all_models_comparison.json`
- `gis-server/docs/s2_hgt_progress.md`
- `gis-server/scripts/build_subset_graph.py`
- `gis-server/scripts/train_s2hgt.py`
- `gis-server/src/models/realestate.py`
- `gis-server/scripts/etl/load_scraped_projects.py`

---

## 20. Immediate Next Step

The next execution step should be:

- audit and materialize the combined Treasury + listing sale-only modeling table
- confirm exact-price coverage, date coverage, duplicate risk, and image coverage
- then start `C0 -> C4`
