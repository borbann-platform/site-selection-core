"""Feature extraction service for price prediction model."""

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class PropertyFeatures:
    """All features extracted for a property - matches training features."""

    # Intrinsic features
    building_area: float
    land_area: float
    building_age: float
    no_of_floor: float
    building_style_encoded: int

    # Spatial features
    transit_stops_1km: int
    bus_stops_500m: int
    schools_2km: int
    pois_500m: int

    # District context
    district_avg_price_sqm: float


# Building style encoding (most common types)
BUILDING_STYLE_ENCODING = {
    "บ้านเดี่ยว": 1,
    "ทาวน์เฮ้าส์": 2,
    "บ้านแฝด": 3,
    "อาคารพาณิชย์": 4,
    "ตึกแถว": 5,
}

# Feature names - must match training script
FEATURE_NAMES = [
    "building_area",
    "land_area",
    "building_age",
    "no_of_floor",
    "building_style",
    "transit_stops_1km",
    "bus_stops_500m",
    "schools_2km",
    "pois_500m",
    "district_avg_price_sqm",
]

# Human-readable display names
FEATURE_DISPLAY_NAMES = {
    "building_area": "Building Area",
    "land_area": "Land Area",
    "building_age": "Building Age",
    "no_of_floor": "Number of Floors",
    "building_style": "Building Type",
    "transit_stops_1km": "Transit Stops (1km)",
    "bus_stops_500m": "Bus Stops (500m)",
    "schools_2km": "Schools (2km)",
    "pois_500m": "Nearby Amenities",
    "district_avg_price_sqm": "District Price Level",
}


class FeatureExtractionService:
    """Extracts features for price prediction from property and spatial data."""

    def __init__(self):
        self._district_avg_cache: dict[str, float] = {}

    def _encode_building_style(self, style: str | None) -> int:
        """Encode building style to numeric value."""
        if style is None:
            return 0
        return BUILDING_STYLE_ENCODING.get(style, 0)

    def _get_district_avg_price_sqm(self, db: Session, amphur: str | None) -> float:
        """Get average price per sqm for a district."""
        if not amphur:
            return 0.0

        if amphur in self._district_avg_cache:
            return self._district_avg_cache[amphur]

        result = db.execute(
            text(
                """
                SELECT AVG(total_price / NULLIF(building_area, 0)) as avg_price_sqm
                FROM house_prices
                WHERE amphur = :amphur
                  AND total_price > 0
                  AND building_area > 0
                """
            ),
            {"amphur": amphur},
        ).fetchone()

        avg = result[0] if result and result[0] else 0.0
        self._district_avg_cache[amphur] = avg
        return avg

    def _count_pois_nearby(
        self, db: Session, lat: float, lon: float, radius_m: int = 500
    ) -> int:
        """Count POIs within radius."""
        result = db.execute(
            text(
                """
                SELECT COUNT(*) as cnt
                FROM view_all_pois
                WHERE ST_DWithin(
                    geometry::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                """
            ),
            {"lat": lat, "lon": lon, "radius": radius_m},
        ).fetchone()

        return result[0] if result else 0

    def _count_transit_nearby(
        self, db: Session, lat: float, lon: float, radius_m: int = 1000
    ) -> int:
        """Count transit stops within radius."""
        result = db.execute(
            text(
                """
                SELECT COUNT(*) as cnt
                FROM transit_stops
                WHERE ST_DWithin(
                    geometry::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                """
            ),
            {"lat": lat, "lon": lon, "radius": radius_m},
        ).fetchone()

        return result[0] if result else 0

    def _count_bus_stops_nearby(
        self, db: Session, lat: float, lon: float, radius_m: int = 500
    ) -> int:
        """Count bus stops within radius."""
        result = db.execute(
            text(
                """
                SELECT COUNT(*) as cnt
                FROM bus_shelters
                WHERE ST_DWithin(
                    geometry::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                """
            ),
            {"lat": lat, "lon": lon, "radius": radius_m},
        ).fetchone()
        return result[0] if result else 0

    def _count_schools_nearby(
        self, db: Session, lat: float, lon: float, radius_m: int = 2000
    ) -> int:
        """Count schools within radius."""
        result = db.execute(
            text(
                """
                SELECT COUNT(*) as cnt
                FROM schools
                WHERE ST_DWithin(
                    geometry::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                """
            ),
            {"lat": lat, "lon": lon, "radius": radius_m},
        ).fetchone()
        return result[0] if result else 0

    def extract_features(
        self,
        db: Session,
        property_id: int,
        lat: float,
        lon: float,
        building_area: float | None,
        land_area: float | None,
        building_age: float | None,
        no_of_floor: float | None,
        building_style: str | None,
        amphur: str | None,
    ) -> PropertyFeatures:
        """Extract all features for a property - matches training features."""
        # Get spatial counts
        transit_count = self._count_transit_nearby(db, lat, lon, 1000)
        bus_count = self._count_bus_stops_nearby(db, lat, lon, 500)
        schools_count = self._count_schools_nearby(db, lat, lon, 2000)
        pois_count = self._count_pois_nearby(db, lat, lon, 500)

        # Get district average
        district_avg = self._get_district_avg_price_sqm(db, amphur)

        return PropertyFeatures(
            building_area=building_area or 0.0,
            land_area=land_area or 0.0,
            building_age=building_age or 10.0,
            no_of_floor=no_of_floor or 1.0,
            building_style_encoded=self._encode_building_style(building_style),
            transit_stops_1km=transit_count,
            bus_stops_500m=bus_count,
            schools_2km=schools_count,
            pois_500m=pois_count,
            district_avg_price_sqm=district_avg,
        )

    def features_to_array(self, features: PropertyFeatures) -> list[float]:
        """Convert PropertyFeatures to array for model input - matches training."""
        return [
            features.building_area,
            features.land_area,
            features.building_age,
            features.no_of_floor,
            float(features.building_style_encoded),
            float(features.transit_stops_1km),
            float(features.bus_stops_500m),
            float(features.schools_2km),
            float(features.pois_500m),
            features.district_avg_price_sqm,
        ]

    @staticmethod
    def feature_names() -> list[str]:
        """Get ordered list of feature names."""
        return FEATURE_NAMES

    @staticmethod
    def feature_display_names() -> dict[str, str]:
        """Get display name mapping."""
        return FEATURE_DISPLAY_NAMES


# Singleton instance
feature_extraction_service = FeatureExtractionService()
        ]


# Singleton instance
feature_extraction_service = FeatureExtractionService()
