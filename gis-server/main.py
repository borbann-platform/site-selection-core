from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes.admin import router as admin_router
from src.routes.analytics import router as analytics_router
from src.routes.auth import router as auth_router
from src.routes.catchment import catchment_service
from src.routes.catchment import router as catchment_router
from src.routes.chat import router as chat_router
from src.routes.chat_sessions import router as chat_sessions_router
from src.routes.hgt_prediction import router as hgt_prediction_router
from src.routes.house_prices import router as house_prices_router
from src.routes.invitations import router as invitations_router
from src.routes.location_intelligence import router as location_intelligence_router
from src.routes.organizations import router as organizations_router
from src.routes.price_prediction import router as price_prediction_router
from src.routes.projects import router as projects_router
from src.routes.site import router as site_router
from src.routes.teams import router as teams_router
from src.routes.transit import router as transit_router
from src.routes.valuation import router as valuation_router


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
app.include_router(chat_sessions_router, prefix="/api/v1", tags=["Chat Sessions"])
app.include_router(
    location_intelligence_router, prefix="/api/v1", tags=["Location Intelligence"]
)
app.include_router(price_prediction_router, prefix="/api/v1", tags=["Price Prediction"])
app.include_router(
    hgt_prediction_router, prefix="/api/v1", tags=["HGT Price Prediction"]
)
app.include_router(transit_router, prefix="/api/v1", tags=["Transit"])
app.include_router(admin_router, prefix="/api/v1", tags=["Admin"])
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(valuation_router, prefix="/api/v1", tags=["Property Valuation"])

# Enterprise auth routers
app.include_router(organizations_router, prefix="/api/v1", tags=["Organizations"])
app.include_router(teams_router, prefix="/api/v1", tags=["Teams"])
app.include_router(invitations_router, prefix="/api/v1", tags=["Invitations"])


@app.get("/", tags=["Root"])
def read_root():
    """A simple endpoint to confirm the API is running."""
    return {"status": "API is running"}
