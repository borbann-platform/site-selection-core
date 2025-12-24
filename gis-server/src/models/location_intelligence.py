"""Pydantic models for Location Intelligence API."""

from pydantic import BaseModel, Field


class LocationRequest(BaseModel):
    """Request model for location intelligence analysis."""

    latitude: float = Field(..., example=13.7563)
    longitude: float = Field(..., example=100.5018)
    radius_meters: int = Field(1000, example=1000)


class TransitDetail(BaseModel):
    """Details about a nearby transit option."""

    name: str
    type: str  # "bts", "mrt", "arl", "bus", "ferry"
    distance_m: float


class TransitScore(BaseModel):
    """Transit accessibility score and details."""

    score: int = Field(..., ge=0, le=100)
    nearest_rail: TransitDetail | None = None
    bus_stops_500m: int = 0
    ferry_access: TransitDetail | None = None
    description: str = ""


class SchoolDetail(BaseModel):
    """Details about a nearby school."""

    name: str
    level: str  # "primary", "secondary", "high", "international"
    distance_m: float


class SchoolsScore(BaseModel):
    """Schools accessibility score and details."""

    score: int = Field(..., ge=0, le=100)
    total_within_2km: int = 0
    by_level: dict[str, int] = {}  # {"primary": 3, "secondary": 2}
    nearest: SchoolDetail | None = None
    description: str = ""


class WalkabilityCategory(BaseModel):
    """Count of amenities by category within walking distance."""

    category: str
    count: int
    examples: list[str] = []


class WalkabilityScore(BaseModel):
    """Walkability score based on nearby amenities."""

    score: int = Field(..., ge=0, le=100)
    categories: list[WalkabilityCategory] = []
    total_amenities: int = 0
    description: str = ""


class FloodRiskScore(BaseModel):
    """Flood risk assessment for the location."""

    level: str = "unknown"  # "low", "medium", "high", "unknown"
    risk_group: int | None = None  # 1 = high priority, 2 = secondary
    district_warnings: list[str] = []
    description: str = ""


class NoiseScore(BaseModel):
    """Noise level estimate based on proximity to major roads."""

    level: str = "unknown"  # "quiet", "moderate", "busy"
    nearest_highway_m: float | None = None
    nearest_major_road_m: float | None = None
    description: str = ""


class LocationIntelligenceResponse(BaseModel):
    """Complete location intelligence analysis response."""

    transit: TransitScore
    schools: SchoolsScore
    walkability: WalkabilityScore
    flood_risk: FloodRiskScore
    noise: NoiseScore
    composite_score: int = Field(..., ge=0, le=100)
    location: dict = {}  # {"lat": ..., "lon": ...}
