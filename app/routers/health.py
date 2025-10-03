"""
Health check router for monitoring service status.
"""
from fastapi import APIRouter, HTTPException, status
from app.redis_manager import redis_manager
from app.database import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        Dictionary with service status
    """
    return {
        "status": "healthy",
        "service": "77x-coupon-service",
        "version": "1.0.0"
    }


@router.get("/health/redis")
async def redis_health():
    """
    Redis health check endpoint.
    
    Returns:
        Dictionary with Redis connection status
    """
    try:
        is_connected = await redis_manager.ping()
        if is_connected:
            return {
                "status": "healthy",
                "service": "redis",
                "connected": True
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis connection failed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis health check failed: {str(e)}"
        )


@router.get("/health/database")
async def database_health():
    """
    Database health check endpoint.
    
    Returns:
        Dictionary with database connection status
    """
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        return {
            "status": "healthy",
            "service": "postgresql",
            "connected": True
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database health check failed: {str(e)}"
        )


@router.get("/health/full")
async def full_health_check():
    """
    Comprehensive health check for all services.
    
    Returns:
        Dictionary with status of all services
    """
    health_status = {
        "status": "healthy",
        "service": "77x-coupon-service",
        "version": "1.0.0",
        "services": {}
    }
    
    # Check Redis
    try:
        redis_connected = await redis_manager.ping()
        health_status["services"]["redis"] = {
            "status": "healthy" if redis_connected else "unhealthy",
            "connected": redis_connected
        }
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check Database
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        health_status["services"]["database"] = {
            "status": "healthy",
            "connected": True
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Determine overall status
    if health_status["status"] == "degraded":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    
    return health_status