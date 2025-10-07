from fastapi import APIRouter, Depends, HTTPException, status

from app.services.coupon_service import CouponService
from app.services.auth_service import AuthService
from app.dependencies import get_current_user
from app.schemas.tokens import TokenValidationRequest, TokenUsageRequest

router = APIRouter()


# Initialize services
coupon_service = CouponService()
auth_service = AuthService()


@router.post("/generate")
async def generate_coupon(
        current_user=Depends(get_current_user),
):
    return await coupon_service.generate_coupon(current_user.user_id)
