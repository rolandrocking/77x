"""
Main FastAPI application entry point.
"""
import logging
from fastapi import FastAPI

from app.database import init_db
from app.routers import auth, coupons, health

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Coupon Token Service",
    description="A microservice that generates coupon tokens with a hard limit of 77 total issued tokens",
    version="1.0.0"
)

# Startup event to initialize database
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    await init_db()
    logger.info("Database initialized")

# Include routers
app.include_router(auth.router)
app.include_router(coupons.router)
app.include_router(health.router)

