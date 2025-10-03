"""
Main FastAPI application entry point.
"""
import logging
import multiprocessing
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.helpers.migrations import apply_migrations
from app.routers import auth, coupons, health

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform any startup logic here
    logger.info("Starting up...")
    logger.info("Run alembic upgrade head...")
    process = multiprocessing.Process(target=apply_migrations)
    process.start()
    process.join()
    # Wait for the process to finish
    logger.info("Finished alembic upgrade.")
    yield  # Control returns to the application during runtime


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for coupon token generation service",
    version="0.1.0",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(coupons.router, prefix="/coupons", tags=["Coupons"])
app.include_router(health.router, prefix="/health", tags=["HealthCheck"])
