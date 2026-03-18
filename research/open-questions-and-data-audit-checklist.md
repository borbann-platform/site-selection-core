# Open Questions And Data Audit Checklist

Use this document before and during benchmark construction.

---

## 1. Purpose

This checklist exists to make sure the combined Treasury + listing benchmark is:

- source-aware
- leakage-safe
- label-clean enough to trust
- ready for multimodal experiments later

This document should be completed before trusting any benchmark comparison.

---

## 2. Locked Benchmark Assumptions

- task = sale price prediction
- benchmark = combined Treasury + listing
- initial target = `log1p(price_thb)`
- initial listing label policy = exact-price sale listings only
- primary split = source-aware time split
- secondary split = grouped spatial / duplicate-safe split

If any of these assumptions change, record it in the decision log.

---

## 3. Source Inventory

### Treasury
- [ ] confirm final source table/file
- [ ] confirm row count
- [ ] confirm available date field
- [ ] confirm target field
- [ ] confirm structured feature coverage

### Listing Sources
- [ ] Baania included
- [ ] Hipflat included
- [ ] private appraisal/listing source included
- [ ] confirm row count by source
- [ ] confirm exact sale label availability by source
- [ ] confirm date field by source
- [ ] confirm image availability by source

Notes:
- 

---

## 4. Label Audit

### Price Definition
- [ ] confirm all rows are sale rows, not rent
- [ ] confirm target is in THB
- [ ] confirm exact-price rows are identifiable
- [ ] quantify range-price rows (`price_start`, `price_end`)
- [ ] confirm no mixed pricing unit contamination

### Date Definition
- [ ] Treasury uses `updated_date`
- [ ] listings use `scraped_at` or best available proxy
- [ ] date coverage is sufficient for time-based split

### Label Quality Risks
- [ ] stale listing risk assessed
- [ ] inflated asking price risk acknowledged
- [ ] repeated listing price changes assessed
- [ ] source-specific label bias assessed

Notes:
- 

---

## 5. Schema Alignment Audit

For the unified modeling table, verify availability and quality of:

### Core Numeric Fields
- [ ] price
- [ ] area_sqm
- [ ] land_area
- [ ] floors
- [ ] building_age
- [ ] latitude
- [ ] longitude

### Core Categorical Fields
- [ ] property_type
- [ ] district
- [ ] subdistrict
- [ ] source_type
- [ ] source_site

### Listing-Only Fields
- [ ] bedrooms
- [ ] bathrooms
- [ ] furnishing
- [ ] facilities
- [ ] developer
- [ ] completion date
- [ ] title
- [ ] description

### Image Fields
- [ ] has_images
- [ ] image_count
- [ ] main_image_url
- [ ] fetched image coverage

Missingness summary:

| Field | Treasury missing % | Listing missing % | Notes |
|---|---:|---:|---|
| price |  |  |  |
| area_sqm |  |  |  |
| floors |  |  |  |
| property_type |  |  |  |
| district |  |  |  |
| event_date |  |  |  |
| image_count |  |  |  |

---

## 6. Duplicate And Leakage Audit

### Listing Duplicate Risk
- [ ] `source + source_listing_id` checked
- [ ] repost frequency estimated
- [ ] duplicate title/address patterns checked
- [ ] duplicate image patterns checked

### Cross-Source Duplicate Risk
- [ ] Treasury vs listings overlap estimated
- [ ] approximate property fingerprint defined
- [ ] duplicate grouping rule drafted

### Leakage Controls
- [ ] no duplicate group split across train/test
- [ ] no future listing snapshot leaks into past benchmark
- [ ] no fold-safe aggregates built from future rows

Proposed duplicate grouping fields:
- exact group:
- fuzzy group:

Notes:
- 

---

## 7. Time-Split Readiness Audit

- [ ] enough historical depth exists for Treasury
- [ ] enough historical depth exists for listings
- [ ] no source has severe date sparsity
- [ ] candidate train/val/test windows proposed

Suggested split table:

| Source | Train Window | Val Window | Test Window | Notes |
|---|---|---|---|---|
| Treasury |  |  |  |  |
| Baania |  |  |  |  |
| Hipflat |  |  |  |  |
| Private |  |  |  |  |

---

## 8. Geography Audit

- [ ] Bangkok-only vs extended area confirmed
- [ ] district coverage by source summarized
- [ ] sparse districts identified
- [ ] coordinate quality checked
- [ ] H3 coverage checked

Optional table:

| Geography Slice | Treasury Rows | Listing Rows | Notes |
|---|---:|---:|---|
| Bangkok core |  |  |  |
| Bangkok outer |  |  |  |
| Non-Bangkok |  |  |  |

---

## 9. Property-Type Audit

- [ ] final sale property types enumerated
- [ ] mapping between Treasury and listing property types drafted
- [ ] low-volume property types identified
- [ ] decision made: one global model vs segmented models

Suggested table:

| Property Type | Treasury Rows | Listing Rows | Exact Price Coverage | Image Coverage | Keep In Phase 1? |
|---|---:|---:|---:|---:|---|
|  |  |  |  |  |  |
|  |  |  |  |  |  |

---

## 10. Image Audit

### Availability
- [ ] % listings with image URLs
- [ ] % listings with fetched image files
- [ ] avg images per listing
- [ ] median images per listing

### Quality
- [ ] duplicate image rate estimated
- [ ] low-resolution rate estimated
- [ ] non-property image frequency estimated
- [ ] watermark/logo/contact-card frequency estimated
- [ ] floorplan/map frequency estimated

### Operational Readiness
- [ ] enough fetched images for pilot
- [ ] top-1/top-3 extraction strategy chosen
- [ ] storage path confirmed

Suggested table:

| Source | Listings | Has image URL | Has fetched image | Avg image count | Notes |
|---|---:|---:|---:|---:|---|
| Baania |  |  |  |  |  |
| Hipflat |  |  |  |  |  |
| Private |  |  |  |  |  |

---

## 11. Feature Readiness Audit

### Baseline Features
- [ ] structured common features ready
- [ ] source markers ready
- [ ] missingness flags ready
- [ ] H3 features ready
- [ ] distance features ready
- [ ] `hex2vec` ready

### Optional Features
- [ ] listing metadata clean enough
- [ ] text-lite features feasible
- [ ] text embeddings deferred or planned

Notes:
- 

---

## 12. Benchmark Gating Questions

Answer these before declaring the benchmark trustworthy.

- [ ] Do we know the final row count by source?
- [ ] Do we know exact-price listing coverage?
- [ ] Do we know image coverage after fetch filtering?
- [ ] Do we know duplicate/repost risk?
- [ ] Do we have a valid source-aware time split?
- [ ] Do we have a secondary leakage-resistant grouped split?
- [ ] Do we have a clear property-type mapping?
- [ ] Do we know whether one global model is reasonable?

Current grouped benchmark state on 2026-03-12:

- [x] Do we know the final row count by source?
- [x] Do we know exact-price listing coverage?
- [x] Do we know image coverage after fetch filtering?
- [x] Do we know duplicate/repost risk?
- [ ] Do we have a valid source-aware time split?
- [x] Do we have a secondary leakage-resistant grouped split?
- [x] Do we have a clear property-type mapping?
- [x] Do we know whether one global model is reasonable?

Grouped split artifact now exists at `gis-server/data/benchmarks/combined_sales_v1_grouped_cv_splits.parquet`.
The current grouping rule is `property_type + h3_res7 spatial cell` with balanced `GroupKFold` folds.

---

## 13. Open Questions To Resolve

### High Priority
- [ ] exact final target choice: `log(price)` only, or also test `log(price_per_sqm)`
- [ ] one global model or segmented by property type
- [ ] exact listing date field for benchmark split
- [ ] whether private source behaves more like Treasury or listings

### Medium Priority
- [ ] whether listing metadata is strong enough to add before images
- [ ] whether text-lite features should enter at `C5`
- [ ] whether price-range rows should be introduced in phase 2

### Later Questions
- [ ] whether image nodes are worth testing in HGT
- [ ] whether source-specific residual modeling is needed

---

## 14. Decision Log

| Date | Topic | Decision | Reason |
|---|---|---|---|
| 2026-03-12 | Unified dataset v1 | Use Treasury + Baania exact-price project rows only for `combined_sales_v1` | This is the only listing source currently normalized with usable exact-price, geo, and unit metadata on the local machine |
| 2026-03-12 | Listing benchmark posture | Treat listing time split as not yet trustworthy | Current listing coverage is a single scrape session on 2026-02-13, so time generalization cannot be validated yet |
| 2026-03-13 | Legacy bulk listing source | Keep `real_estate_listings` out of the main benchmark for now, but treat it as a high-priority controlled expansion candidate | Audit shows a potentially salvageable Bangkok sale-like subset far larger than the current clean listing benchmark, but source-file labels are noisy and `last_updated` is empty |

---

## 15. Exit Criteria For Starting Experiments

We can begin `C0 -> C4` only when:

- [ ] unified table schema is defined
- [ ] exact-price sale listing policy is implemented
- [ ] source-aware time split is defined
- [ ] duplicate grouping logic is defined
- [ ] feature coverage is quantified
- [ ] benchmark reporting template is ready

Current state on 2026-03-12:

- [x] unified table schema is defined
- [x] exact-price sale listing policy is implemented
- [ ] source-aware time split is defined
- [x] duplicate grouping logic is defined
- [x] feature coverage is quantified
- [x] benchmark reporting template is ready

Observed audit snapshot from `combined_sales_v1`:

- final row count by source:
  - Treasury: `8,514`
  - Baania exact-price listings: `417`
- listing image coverage:
  - has image URL: `91.4%`
  - has uploaded images: `16.1%`
- listing duplicate risk:
  - exact duplicate groups: `0`
  - fuzzy duplicate keys: `1`
- critical blocker:
  - listing dates come from a single scrape session, so benchmark trust is still capped by split quality

We can begin `M1` only when:

- [ ] best combined non-image baseline is selected
- [ ] fetched image coverage is known
- [ ] embedding extraction path is confirmed
- [ ] top-k image policy is chosen

We can begin `G1` only when:

- [ ] best multimodal tabular baseline is known
- [ ] graph advantage hypothesis is explicit
- [ ] HGT is evaluated against the right benchmark, not an outdated baseline
