"""
Coupon router for token generation and management endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis

from app.config import settings
from app.models import (
    CouponResponse, 
    TokenValidationResponse, 
    StatsResponse, 
    UserStatsResponse,
    TokenUsageResponse
)
from app.services.coupon_service import CouponService
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Router instance
router = APIRouter(tags=["coupons"])

# Security scheme
security = HTTPBearer()

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


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Get current user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User ID from the token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    auth_service = AuthService()
    user_id = auth_service.verify_auth_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


@router.post("/generate-coupon", response_model=CouponResponse)
async def generate_coupon(
    current_user_id: str = Depends(get_current_user)
):
    """
    Generate a new coupon token if under the limits.
    
    Args:
        current_user_id: ID of the authenticated user
        
    Returns:
        Coupon response with token information
        
    Raises:
        HTTPException: If limits are exceeded or service is unavailable
    """
    coupon_service = CouponService(redis_client)
    result = coupon_service.generate_coupon(current_user_id)
    return CouponResponse(**result)


@router.post("/validate-token", response_model=TokenValidationResponse)
async def validate_token(token: str):
    """
    Validate a coupon token and check if it's been used.
    
    Args:
        token: JWT token to validate
        
    Returns:
        Token validation response
        
    Raises:
        HTTPException: If service is unavailable
    """
    coupon_service = CouponService(redis_client)
    result = coupon_service.validate_token(token)
    return TokenValidationResponse(**result)


@router.post("/use-token", response_model=TokenUsageResponse)
async def use_token(token: str):
    """
    Mark a token as used (single-use enforcement).
    
    Args:
        token: JWT token to mark as used
        
    Returns:
        Token usage confirmation
        
    Raises:
        HTTPException: If token is invalid, expired, or already used
    """
    coupon_service = CouponService(redis_client)
    result = coupon_service.use_token(token)
    return TokenUsageResponse(**result)


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get current statistics about token usage.
    
    Returns:
        Global token usage statistics
        
    Raises:
        HTTPException: If service is unavailable
    """
    coupon_service = CouponService(redis_client)
    result = coupon_service.get_stats()
    return StatsResponse(**result)


@router.get("/user-stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user_id: str = Depends(get_current_user)
):
    """
    Get current user's token statistics.
    
    Args:
        current_user_id: ID of the authenticated user
        
    Returns:
        User's token usage statistics
        
    Raises:
        HTTPException: If service is unavailable
    """
    coupon_service = CouponService(redis_client)
    result = coupon_service.get_user_stats(current_user_id)
    return UserStatsResponse(**result)
