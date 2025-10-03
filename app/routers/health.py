from fastapi import APIRouter, HTTPException, status
from app.managers.redis_manager import redis_manager
from app.core.database import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "77x-coupon-service",
        "version": "1.0.0"
    }


@router.get("/redis")
async def redis_health():
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


@router.get("/database")
async def database_health():
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


@router.get("/full")
async def full_health_check():
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
