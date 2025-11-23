from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes.analytics import router as analytics_router
from src.routes.catchment import catchment_service
from src.routes.catchment import router as catchment_router
from src.routes.projects import router as projects_router
from src.routes.site import router as site_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load graph on startup
    catchment_service.load_graph()
    yield
    # Clean up resources if needed


app = FastAPI(
    title="GIS Analysis API",
    description="An API for performing geospatial analysis.",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
origins = [
    "http://localhost:5173",  # Vite default
    "http://localhost:3000",  # Alternative
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers from the routes module
# Include site routes at the application root so `POST /analyze-site` is available
app.include_router(site_router, prefix="/api/v1", tags=["Site Analysis"])
app.include_router(catchment_router, prefix="/api/v1", tags=["Catchment Analysis"])
app.include_router(projects_router, prefix="/api/v1", tags=["Projects"])
app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])


@app.get("/", tags=["Root"])
def read_root():
    """A simple endpoint to confirm the API is running."""
    return {"status": "API is running"}
