from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes.analytics import router as analytics_router
from src.routes.catchment import catchment_service
from src.routes.catchment import router as catchment_router
from src.routes.chat import router as chat_router
from src.routes.house_prices import router as house_prices_router
from src.routes.location_intelligence import router as location_intelligence_router
from src.routes.projects import router as projects_router
from src.routes.site import router as site_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load graph on startup
    catchment_service.load_graph()
    yield
    # Clean up resources if needed


app = FastAPI(
    title="Real Estate Information Platform API",
    description="An API for real estate information, price prediction AI, and property analysis.",
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
app.include_router(site_router, prefix="/api/v1", tags=["Site Analysis"])
app.include_router(catchment_router, prefix="/api/v1", tags=["Catchment Analysis"])
app.include_router(projects_router, prefix="/api/v1", tags=["Projects"])
app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])
app.include_router(house_prices_router, prefix="/api/v1", tags=["House Prices"])
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(
    location_intelligence_router, prefix="/api/v1", tags=["Location Intelligence"]
)


@app.get("/", tags=["Root"])
def read_root():
    """A simple endpoint to confirm the API is running."""
    return {"status": "API is running"}
