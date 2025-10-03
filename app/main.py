"""
Main FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import init_db
from app.routers import auth, coupons, health
from app.managers.redis_manager import redis_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform any startup logic here
    logger.info("Starting up...")
    logger.info("Run alembic upgrade head...")
    # Wait for the process to finish
    logger.info("Finished alembic upgrade.")
    yield  # Control returns to the application during runtime


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for graph data analysis with AI suggestions",
    version="0.1.0",
    openapi_url=f"{settings.API_SERVICE_STR}/openapi.json",
    lifespan=lifespan,
    debug=settings.debug,
    docs_url=f"{settings.API_SERVICE_STR}/docs",
    redoc_url=f"{settings.API_SERVICE_STR}/redoc"
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(coupons.router, prefix="/coupons", tags=["Coupons"])
app.include_router(health.router, prefix="/health", tags=["HealthCheck"])
