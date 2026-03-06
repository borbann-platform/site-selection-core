export const SCORE_METHODOLOGY = {
  composite:
    "Weighted blend: Transit 25%, Walkability 25%, Schools 20%, Flood safety 15%, Noise comfort 15%.",
  transit:
    "Transit score adds points for nearest rail distance (<=400m: +40, <=800m: +30, <=1000m: +20), bus stop density within 500m (>=5: +30, >=3: +20, >=1: +10), and ferry access bonus (<=500m: +20, <=1000m: +10). Capped at 100.",
  walkability:
    "Walkability checks 8 amenity categories within ~800m (restaurant, cafe, grocery, pharmacy, bank, park, gym, retail). Each category adds +12.5 when count >=3, or +8 when count >=1. Capped at 100.",
  schools:
    "Schools score uses count within 2km: >=10 => 80, >=5 => 60, >=2 => 40, >=1 => 20; plus diversity bonus by level (>=3 levels: +20, >=2 levels: +10). Capped at 100.",
  floodRisk:
    "Flood risk matches nearest district with flood-warning records. risk_group 1 => high, risk_group 2 => medium, no warnings => low.",
  noise:
    "Noise is a proximity proxy to major roads using nearest gas station and traffic point distances. <100m => busy, <300m => moderate, otherwise quiet.",
  districtTrend:
    "District trend is shown from market insight aggregates for the selected area. Exact trend derivation source is pending confirmation.",
} as const;
