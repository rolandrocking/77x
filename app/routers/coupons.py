"""
Coupon router for token generation and management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.services.coupon_service import CouponService
from app.services.auth_service import AuthService
from app.dependencies import get_current_user
from app.schemas import TokenValidationRequest, TokenUsageRequest

router = APIRouter(prefix="/coupons", tags=["coupons"])


# Initialize services
coupon_service = CouponService()
auth_service = AuthService()


@router.post("/generate")
async def generate_coupon(current_user=Depends(get_current_user)):
    """
    Generate a new coupon token.
    
    Returns:
        Dictionary containing the generated token and metadata
    """
    return await coupon_service.generate_coupon(current_user.user_id)


@router.post("/validate")
async def validate_token(request: TokenValidationRequest):
    """
    Validate a coupon token.
    
    Args:
        request: Token validation request
        
    Returns:
        Dictionary containing validation result
    """
    return await coupon_service.validate_token(request.token)


@router.post("/use")
async def use_token(request: TokenUsageRequest):
    """
    Mark a coupon token as used.
    
    Args:
        request: Token usage request
        
    Returns:
        Dictionary containing usage confirmation
    """
    return await coupon_service.use_token(request.token)


@router.get("/stats")
async def get_stats():
    """
    Get current statistics about token usage.
    
    Returns:
        Dictionary containing usage statistics
    """
    return await coupon_service.get_stats()


@router.get("/user-stats")
async def get_user_stats(current_user=Depends(get_current_user)):
    """
    Get current user's token statistics.
    
    Returns:
        Dictionary containing user's token statistics
    """
    return await coupon_service.get_user_stats(current_user.user_id)
