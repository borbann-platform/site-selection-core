from pydantic import BaseModel, Field


# 1. Define the Input Model for the analysis endpoint
class SiteRequest(BaseModel):
    latitude: float = Field(..., example=13.7563)
    longitude: float = Field(..., example=100.5018)
    radius_meters: int = Field(500, example=500)
    target_category: str = Field(..., example="cafe")


# 2. Define the nested models for the Response
class AnalysisSummary(BaseModel):
    competitors_count: int
    magnets_count: int
    traffic_potential: str
    total_population: int = 0


class AnalysisDetails(BaseModel):
    nearby_competitors: list[str] | None = None
    nearby_magnets: list[str] | None = None


# 3. Define the main Response Model
class SiteResponse(BaseModel):
    site_score: float
    summary: AnalysisSummary
    details: AnalysisDetails
    location_warning: str | None = None


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: dict
    properties: dict


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]


# 4. Define the Input Model for the nearby endpoint
class NearbyRequest(BaseModel):
    latitude: float = Field(..., example=13.7563)
    longitude: float = Field(..., example=100.5018)
    radius_meters: int = Field(500, example=500)
    categories: list[str] = Field(..., example=["cafe", "school"])
