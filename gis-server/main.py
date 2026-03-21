from contextlib import asynccontextmanager
import logging
import time
import uuid

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from sqlalchemy import text
from src.config.settings import settings
from src.config.database import engine
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
from src.routes.listings import router as listings_router
from src.routes.observability import router as observability_router
from src.routes.organizations import router as organizations_router
from src.routes.price_prediction import router as price_prediction_router
from src.routes.projects import router as projects_router
from src.routes.site import router as site_router
from src.routes.teams import router as teams_router
from src.routes.transit import router as transit_router
from src.routes.valuation import router as valuation_router
from src.services.observability import request_metrics
from src.services.listings_tile_refresh import listings_tile_refresh_manager
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load graph on startup
    catchment_service.load_graph()
    listings_tile_refresh_manager.start()
    yield
    # Clean up resources if needed
    listings_tile_refresh_manager.stop()


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


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    response: Response

    try:
        response = await call_next(request)
    except SQLAlchemyTimeoutError:
        duration_ms = (time.perf_counter() - start) * 1000
        request_metrics.observe_request(
            method=request.method,
            path=request.url.path,
            status_code=503,
            duration_seconds=duration_ms / 1000,
        )
        logger.exception(
            "request_failed_db_pool_timeout method=%s path=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            request_id,
            duration_ms,
        )
        return Response(
            content='{"detail":"Service temporarily overloaded"}',
            status_code=503,
            media_type="application/json",
            headers={"X-Request-ID": request_id, "Retry-After": "1"},
        )
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        request_metrics.observe_request(
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_seconds=duration_ms / 1000,
        )
        logger.exception(
            "request_failed method=%s path=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            request_id,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    request_metrics.observe_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_seconds=duration_ms / 1000,
    )
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete method=%s path=%s status=%s request_id=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        duration_ms,
    )
    return response


@app.get("/healthz", tags=["Health"])
def healthz():
    """Lightweight liveness probe for load balancers and container healthchecks."""
    return {"status": "ok"}


@app.get("/readyz", tags=["Health"])
def readyz():
    """Readiness probe that verifies the API can reach its database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness_check_failed error=%s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "detail": "database unavailable"},
        )

    return {"status": "ready"}


# Include routers from the routes module
app.include_router(site_router, prefix="/api/v1", tags=["Site Analysis"])
app.include_router(catchment_router, prefix="/api/v1", tags=["Catchment Analysis"])
app.include_router(projects_router, prefix="/api/v1", tags=["Projects"])
app.include_router(analytics_router, prefix="/api/v1", tags=["Analytics"])
app.include_router(house_prices_router, prefix="/api/v1", tags=["House Prices"])
app.include_router(listings_router, prefix="/api/v1", tags=["Listings"])
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
app.include_router(observability_router, prefix="/api/v1", tags=["Observability"])

# Enterprise auth routers
app.include_router(organizations_router, prefix="/api/v1", tags=["Organizations"])
app.include_router(teams_router, prefix="/api/v1", tags=["Teams"])
app.include_router(invitations_router, prefix="/api/v1", tags=["Invitations"])


@app.get("/", tags=["Root"])
def read_root():
    """A simple endpoint to confirm the API is running."""
    return {"status": "API is running"}
