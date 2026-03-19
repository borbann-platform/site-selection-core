"""Location Intelligence Service - calculates transit, walkability, schools, flood, noise scores."""

import csv
import hashlib
import logging
import time
from contextlib import contextmanager
from collections import OrderedDict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session
from src.config.settings import settings
from src.models.location_intelligence import (
    FloodRiskScore,
    LocationIntelligenceResponse,
    NoiseScore,
    SchoolDetail,
    SchoolsScore,
    TransitDetail,
    TransitScore,
    WalkabilityCategory,
    WalkabilityScore,
)
from src.services.observability import location_intelligence_metrics

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Weights for composite score
WEIGHTS = {
    "transit": 0.25,
    "walkability": 0.25,
    "schools": 0.20,
    "flood": 0.15,
    "noise": 0.15,
}

# Walkability categories to check
WALKABILITY_CATEGORIES = [
    ("restaurant", ["restaurant", "food_court"]),
    ("cafe", ["cafe", "coffee_shop", "bakery"]),
    ("grocery", ["supermarket", "convenience_store", "grocery"]),
    ("pharmacy", ["pharmacy", "drugstore"]),
    ("bank", ["bank", "atm"]),
    ("park", ["park", "garden", "playground"]),
    ("gym", ["gym", "fitness_center", "sports_center"]),
    ("retail", ["mall", "shopping_center", "department_store"]),
]


class LocationIntelligenceService:
    """Service for calculating location intelligence scores."""

    def __init__(self):
        self._flood_data: list[dict] | None = None
        self._cache: OrderedDict[str, tuple[LocationIntelligenceResponse, float]] = (
            OrderedDict()
        )
        self._cache_ttl_seconds = settings.LOCATION_INTELLIGENCE_CACHE_TTL_SECONDS
        self._cache_max_entries = settings.LOCATION_INTELLIGENCE_CACHE_MAX_ENTRIES
        self._cache_hits = 0
        self._cache_misses = 0

    def _get_cache_key(self, lat: float, lon: float, radius: int) -> str:
        """Generate cache key based on location grid cell (100m precision)."""
        # Round to ~100m grid cells
        grid_lat = round(lat, 3)
        grid_lon = round(lon, 3)
        key = f"{grid_lat}:{grid_lon}:{radius}"
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> LocationIntelligenceResponse | None:
        now = time.time()
        cached = self._cache.get(cache_key)
        if not cached:
            self._cache_misses += 1
            return None

        response, ts = cached
        if now - ts > self._cache_ttl_seconds:
            del self._cache[cache_key]
            self._cache_misses += 1
            return None

        self._cache.move_to_end(cache_key)
        self._cache_hits += 1
        return response

    def _set_cached(
        self, cache_key: str, response: LocationIntelligenceResponse
    ) -> None:
        self._cache[cache_key] = (response, time.time())
        self._cache.move_to_end(cache_key)
        while len(self._cache) > self._cache_max_entries:
            self._cache.popitem(last=False)

    def get_cache_stats(self) -> dict[str, int | float]:
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total) if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_entries": self._cache_max_entries,
            "ttl_seconds": self._cache_ttl_seconds,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": round(hit_rate, 4),
        }

    def _load_flood_data(self) -> list[dict]:
        """Load flood warning data from CSV."""
        if self._flood_data is not None:
            return self._flood_data

        flood_path = PROJECT_ROOT / "data" / "flood-warning.csv"
        self._flood_data = []

        if not flood_path.exists():
            logger.warning(f"Flood data not found at {flood_path}")
            return self._flood_data

        with flood_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._flood_data.append(
                    {
                        "district": row.get("District", ""),
                        "risk_group": int(row.get("risk_group", 2)),
                        "risk_type": row.get("risk_type", ""),
                        "area": row.get("area", ""),
                    }
                )

        return self._flood_data

    @staticmethod
    def _radius_meters_to_degrees(radius_meters: int) -> float:
        # 1 degree latitude is approximately 111,320 meters.
        return radius_meters / 111_320.0

    @staticmethod
    def _rollback_session(db: Session) -> None:
        try:
            db.rollback()
        except Exception:
            logger.exception("Failed to rollback DB session after stage error")

    @contextmanager
    def _observe_stage(self, stage: str):
        start = time.perf_counter()
        is_error = False
        try:
            yield
        except Exception:
            is_error = True
            raise
        finally:
            duration = time.perf_counter() - start
            location_intelligence_metrics.observe_stage(
                stage=stage,
                duration_seconds=duration,
                is_error=is_error,
            )

    def calculate_transit_score(
        self, db: Session, lat: float, lon: float, radius: int = 1000
    ) -> TransitScore:
        """Calculate transit accessibility score."""
        with self._observe_stage("transit"):
            # Query for nearest rail station (BTS/MRT/ARL)
            rail_query = text(
                """
                WITH nearest AS (
                    SELECT stop_name as name, source as type, geometry
                    FROM transit_stops
                    WHERE source IN ('bangkok-gtfs')
                      AND geometry && ST_Expand(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :radius_deg)
                      AND ST_DWithin(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)
                    ORDER BY geometry <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                    LIMIT 1
                )
                SELECT name, type,
                       ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                FROM nearest
            """
            )

            # Query for bus stops within 500m
            bus_query = text(
                """
                SELECT COUNT(*) as count
                FROM bus_shelters
                WHERE geometry && ST_Expand(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :radius_deg)
                  AND ST_DWithin(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 500)
            """
            )

            # Query for ferry/water transport
            ferry_query = text(
                """
                WITH nearest AS (
                    SELECT name, geometry
                    FROM water_transport_piers
                    WHERE geometry && ST_Expand(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :radius_deg)
                      AND ST_DWithin(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)
                    ORDER BY geometry <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                    LIMIT 1
                )
                SELECT name,
                       ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                FROM nearest
            """
            )

            nearest_rail = None
            bus_count: int = 0
            ferry_access = None
            score = 0

            try:
                radius_deg = self._radius_meters_to_degrees(radius)
                # Nearest rail
                result = db.execute(
                    rail_query,
                    {
                        "lat": lat,
                        "lon": lon,
                        "radius": radius,
                        "radius_deg": radius_deg,
                    },
                )
                row = result.fetchone()
                if row:
                    nearest_rail = TransitDetail(
                        name=row.name or "Unknown",
                        type="rail",
                        distance_m=round(row.distance_m, 0),
                    )
                    # Score based on distance (closer = better)
                    if row.distance_m <= 400:
                        score += 40
                    elif row.distance_m <= 800:
                        score += 30
                    elif row.distance_m <= 1000:
                        score += 20

                # Bus stops
                result = db.execute(
                    bus_query,
                    {
                        "lat": lat,
                        "lon": lon,
                        "radius_deg": self._radius_meters_to_degrees(500),
                    },
                )
                row = result.fetchone()
                if row:
                    bus_count = int(row._mapping.get("count", 0) or 0)
                    # Score based on bus stop density
                    if bus_count >= 5:
                        score += 30
                    elif bus_count >= 3:
                        score += 20
                    elif bus_count >= 1:
                        score += 10

                # Ferry
                result = db.execute(
                    ferry_query,
                    {
                        "lat": lat,
                        "lon": lon,
                        "radius": radius,
                        "radius_deg": radius_deg,
                    },
                )
                row = result.fetchone()
                if row:
                    ferry_access = TransitDetail(
                        name=row.name or "Unknown",
                        type="ferry",
                        distance_m=round(row.distance_m, 0),
                    )
                    # Bonus for ferry access
                    if row.distance_m <= 500:
                        score += 20
                    elif row.distance_m <= 1000:
                        score += 10

            except Exception as e:
                logger.exception(f"Error calculating transit score: {e}")
                self._rollback_session(db)

            # Cap at 100
            score = min(100, score)

            # Generate description
            desc_parts = []
            if nearest_rail:
                desc_parts.append(f"Rail station {int(nearest_rail.distance_m)}m away")
            if bus_count > 0:
                desc_parts.append(f"{bus_count} bus stops nearby")
            if ferry_access:
                desc_parts.append("Ferry access available")

            description = (
                ". ".join(desc_parts) if desc_parts else "Limited transit options"
            )

            return TransitScore(
                score=score,
                nearest_rail=nearest_rail,
                bus_stops_500m=bus_count,
                ferry_access=ferry_access,
                description=description,
            )

    def calculate_schools_score(
        self, db: Session, lat: float, lon: float, radius: int = 2000
    ) -> SchoolsScore:
        """Calculate schools accessibility score."""
        with self._observe_stage("schools"):
            query = text(
                """
                SELECT name, level,
                       ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                FROM schools
                WHERE geometry && ST_Expand(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :radius_deg)
                  AND ST_DWithin(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius)
                ORDER BY distance_m
            """
            )

            schools = []
            by_level: dict[str, int] = {}
            nearest: SchoolDetail | None = None
            score = 0

            try:
                result = db.execute(
                    query,
                    {
                        "lat": lat,
                        "lon": lon,
                        "radius": radius,
                        "radius_deg": self._radius_meters_to_degrees(radius),
                    },
                )
                for row in result:
                    level = self._parse_school_level(row.level or "")
                    schools.append(
                        {
                            "name": row.name,
                            "level": level,
                            "distance_m": row.distance_m,
                        }
                    )
                    by_level[level] = by_level.get(level, 0) + 1

                    if nearest is None:
                        nearest = SchoolDetail(
                            name=row.name or "Unknown",
                            level=level,
                            distance_m=round(row.distance_m, 0),
                        )

            except Exception as e:
                logger.exception(f"Error calculating schools score: {e}")
                self._rollback_session(db)

            total = len(schools)

            # Score based on school availability
            if total >= 10:
                score = 80
            elif total >= 5:
                score = 60
            elif total >= 2:
                score = 40
            elif total >= 1:
                score = 20

            # Bonus for variety of levels
            if len(by_level) >= 3:
                score += 20
            elif len(by_level) >= 2:
                score += 10

            score = min(100, score)

            # Description
            if total > 0:
                description = f"{total} schools within {radius}m"
                if nearest:
                    description += f". Nearest: {int(nearest.distance_m)}m"
            else:
                description = "No schools within range"

            return SchoolsScore(
                score=score,
                total_within_2km=total,
                by_level=by_level,
                nearest=nearest,
                description=description,
            )

    def _parse_school_level(self, level_str: str) -> str:
        """Parse Thai school level to category."""
        level_lower = level_str.lower()
        if "อนุบาล" in level_str:
            return "kindergarten"
        if "ประถม" in level_str:
            return "primary"
        if "มัธยม" in level_str:
            return "secondary"
        if "international" in level_lower or "นานาชาติ" in level_str:
            return "international"
        return "other"

    def calculate_walkability_score(
        self, db: Session, lat: float, lon: float, radius: int = 800
    ) -> WalkabilityScore:
        """Calculate walkability score based on nearby amenities."""
        with self._observe_stage("walkability"):
            categories_result: list[WalkabilityCategory] = []
            total = 0
            score = 0

            walkability_query = text(
                """
                SELECT
                    CASE
                        WHEN type = ANY(:restaurant_types) THEN 'restaurant'
                        WHEN type = ANY(:cafe_types) THEN 'cafe'
                        WHEN type = ANY(:grocery_types) THEN 'grocery'
                        WHEN type = ANY(:pharmacy_types) THEN 'pharmacy'
                        WHEN type = ANY(:bank_types) THEN 'bank'
                        WHEN type = ANY(:park_types) THEN 'park'
                        WHEN type = ANY(:gym_types) THEN 'gym'
                        WHEN type = ANY(:retail_types) THEN 'retail'
                    END AS category,
                    LEAST(COUNT(*), 10) AS poi_count,
                    (ARRAY_REMOVE(ARRAY_AGG(name), NULL))[1:3] AS examples
                FROM view_all_pois
                WHERE ST_DWithin(
                    geometry::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                  AND geometry && ST_Expand(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :radius_deg)
                  AND (
                    type = ANY(:restaurant_types)
                    OR type = ANY(:cafe_types)
                    OR type = ANY(:grocery_types)
                    OR type = ANY(:pharmacy_types)
                    OR type = ANY(:bank_types)
                    OR type = ANY(:park_types)
                    OR type = ANY(:gym_types)
                    OR type = ANY(:retail_types)
                  )
                GROUP BY category
            """
            )

            category_types = {
                "restaurant_types": WALKABILITY_CATEGORIES[0][1],
                "cafe_types": WALKABILITY_CATEGORIES[1][1],
                "grocery_types": WALKABILITY_CATEGORIES[2][1],
                "pharmacy_types": WALKABILITY_CATEGORIES[3][1],
                "bank_types": WALKABILITY_CATEGORIES[4][1],
                "park_types": WALKABILITY_CATEGORIES[5][1],
                "gym_types": WALKABILITY_CATEGORIES[6][1],
                "retail_types": WALKABILITY_CATEGORIES[7][1],
            }

            try:
                result = db.execute(
                    walkability_query,
                    {
                        "lat": lat,
                        "lon": lon,
                        "radius": radius,
                        "radius_deg": self._radius_meters_to_degrees(radius),
                        **category_types,
                    },
                )
                for row in result:
                    row_mapping = row._mapping
                    category_name = row_mapping.get("category")
                    count = int(row_mapping.get("poi_count", 0) or 0)
                    examples = list(row_mapping.get("examples") or [])

                    if not category_name or count <= 0:
                        continue

                    categories_result.append(
                        WalkabilityCategory(
                            category=category_name,
                            count=count,
                            examples=examples,
                        )
                    )
                    total += count

                    # Add to score (each category can contribute up to 12.5 points)
                    if count >= 3:
                        score += 12.5
                    elif count >= 1:
                        score += 8
            except Exception as e:
                logger.exception(f"Error calculating walkability score: {e}")
                self._rollback_session(db)

            score = min(100, int(score))

            # Description
            if total >= 20:
                description = "Excellent walkability - many amenities nearby"
            elif total >= 10:
                description = (
                    "Good walkability - most essentials within walking distance"
                )
            elif total >= 5:
                description = "Moderate walkability - some amenities nearby"
            else:
                description = (
                    "Limited walkability - few amenities within walking distance"
                )

            return WalkabilityScore(
                score=score,
                categories=categories_result,
                total_amenities=total,
                description=description,
            )

    def calculate_flood_risk(
        self, db: Session, lat: float, lon: float
    ) -> FloodRiskScore:
        """Calculate flood risk based on district matching."""
        with self._observe_stage("flood"):
            # First, get the district for this location
            district_query = text(
                """
                SELECT amphur
                FROM house_prices
                WHERE amphur IS NOT NULL
                  AND geometry IS NOT NULL
                ORDER BY geometry <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            """
            )

            district = None
            try:
                result = db.execute(district_query, {"lat": lat, "lon": lon})
                row = result.fetchone()
                if row:
                    district = row.amphur
            except Exception as e:
                logger.exception(f"Error finding district: {e}")
                self._rollback_session(db)

            # Load flood data and check for warnings
            flood_data = self._load_flood_data()
            warnings = []
            risk_group = None

            if district:
                for item in flood_data:
                    # Match district (may be in Thai like "เขตจตุจักร")
                    if district in item["district"] or item["district"] in district:
                        warnings.append(item["area"])
                        if risk_group is None or item["risk_group"] < risk_group:
                            risk_group = item["risk_group"]

            # Determine level
            if risk_group == 1:
                level = "high"
                description = (
                    f"High flood risk area. {len(warnings)} warning zones in district."
                )
            elif risk_group == 2:
                level = "medium"
                description = (
                    f"Moderate flood risk. {len(warnings)} warning zones in district."
                )
            elif warnings:
                level = "medium"
                description = "Some flood warnings in the area."
            else:
                level = "low"
                description = "No flood warnings on record for this area."

            return FloodRiskScore(
                level=level,
                risk_group=risk_group,
                district_warnings=warnings[:5],  # Limit to 5
                description=description,
            )

    def calculate_noise_level(self, db: Session, lat: float, lon: float) -> NoiseScore:
        """Estimate noise level based on proximity to major roads."""
        with self._observe_stage("noise"):
            # Use gas stations as proxy for major roads (they're usually on busy roads)
            # Also check traffic management points
            query = text(
                """
                SELECT
                    (SELECT MIN(ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography))
                     FROM gas_stations) as nearest_gas,
                    (SELECT MIN(ST_Distance(geometry::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography))
                     FROM traffic_points) as nearest_traffic
            """
            )

            nearest_highway = None
            nearest_major = None
            level = "unknown"

            try:
                result = db.execute(query, {"lat": lat, "lon": lon})
                row = result.fetchone()
                if row:
                    nearest_gas = row.nearest_gas
                    nearest_traffic = row.nearest_traffic

                    # Use the closer one as proxy for major road
                    if nearest_gas is not None:
                        nearest_major = nearest_gas
                    if nearest_traffic is not None:
                        if nearest_major is None or nearest_traffic < nearest_major:
                            nearest_highway = nearest_traffic

            except Exception as e:
                logger.exception(f"Error calculating noise level: {e}")
                self._rollback_session(db)

            # Determine level based on distance to major road proxy
            min_dist = min(
                d for d in [nearest_highway, nearest_major, 9999] if d is not None
            )

            if min_dist < 100:
                level = "busy"
                description = "Near major road - expect higher noise levels"
            elif min_dist < 300:
                level = "moderate"
                description = "Moderate distance from major roads"
            else:
                level = "quiet"
                description = "Away from major roads - quieter area"

            return NoiseScore(
                level=level,
                nearest_highway_m=round(nearest_highway, 0)
                if nearest_highway
                else None,
                nearest_major_road_m=round(nearest_major, 0) if nearest_major else None,
                description=description,
            )

    def analyze(
        self, db: Session, lat: float, lon: float, radius: int = 1000
    ) -> LocationIntelligenceResponse:
        """Perform complete location intelligence analysis."""
        with self._observe_stage("analyze_total"):
            # Check cache
            cache_key = self._get_cache_key(lat, lon, radius)
            cached = self._get_cached(cache_key)
            if cached:
                location_intelligence_metrics.observe_stage(
                    "cache_hit", duration_seconds=0.0
                )
                return cached

            location_intelligence_metrics.observe_stage(
                "cache_miss", duration_seconds=0.0
            )

            # Calculate all scores
            transit = self.calculate_transit_score(db, lat, lon, radius)
            schools = self.calculate_schools_score(db, lat, lon, min(radius * 2, 2000))
            walkability = self.calculate_walkability_score(
                db, lat, lon, min(radius, 800)
            )
            flood_risk = self.calculate_flood_risk(db, lat, lon)
            noise = self.calculate_noise_level(db, lat, lon)

            # Calculate composite score
            flood_score = {"low": 100, "medium": 50, "high": 20, "unknown": 50}.get(
                flood_risk.level, 50
            )
            noise_score = {"quiet": 100, "moderate": 70, "busy": 40, "unknown": 50}.get(
                noise.level, 50
            )

            composite = int(
                transit.score * WEIGHTS["transit"]
                + walkability.score * WEIGHTS["walkability"]
                + schools.score * WEIGHTS["schools"]
                + flood_score * WEIGHTS["flood"]
                + noise_score * WEIGHTS["noise"]
            )

            response = LocationIntelligenceResponse(
                transit=transit,
                schools=schools,
                walkability=walkability,
                flood_risk=flood_risk,
                noise=noise,
                composite_score=composite,
                location={"lat": lat, "lon": lon},
            )

            # Cache result
            self._set_cached(cache_key, response)

            return response


# Singleton instance
location_intelligence_service = LocationIntelligenceService()
