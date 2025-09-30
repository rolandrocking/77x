"""
Health check router for monitoring and status endpoints.
"""
import logging
from datetime import datetime
from fastapi import APIRouter
import redis

from app.config import settings
from app.models import HealthResponse

logger = logging.getLogger(__name__)

# Router instance
router = APIRouter(tags=["health"])

# Redis connection
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True
)


def check_redis_connection() -> bool:
    """
    Check if Redis is available.
    
    Returns:
        True if Redis is connected, False otherwise
    """
    try:
        redis_client.ping()
        return True
    except redis.RedisError:
        return False


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint to verify service status.
    
    Returns:
        Health status information including Redis connectivity
    """
    redis_healthy = check_redis_connection()
    
    return HealthResponse(
        status="healthy" if redis_healthy else "degraded",
        redis_connected=redis_healthy,
        timestamp=datetime.utcnow()
    )
