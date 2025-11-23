from pydantic import BaseModel, Field


class CatchmentRequest(BaseModel):
    latitude: float = Field(..., example=13.7563)
    longitude: float = Field(..., example=100.5018)
    minutes: int = Field(10, example=10)
    mode: str = Field("walk", example="walk")


class CatchmentResponse(BaseModel):
    type: str = "Feature"
    geometry: dict
    properties: dict


class CatchmentAnalysisResponse(BaseModel):
    geometry: dict
    population: int
    score: float
