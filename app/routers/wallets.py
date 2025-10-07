"""
FastAPI router for wallet coupon operations.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.dependencies import get_current_user
from app.models.users import User
from app.models.wallets import WalletPass, WalletPassTemplate
from app.schemas.wallets import (
    WalletCouponCreate, WalletCouponResponse, CouponListResponse,
    CouponTemplateCreate, CouponTemplateResponse,
    CouponGenerateRequest, DiscountCouponData
)
from app.services.google_wallet_service import GoogleWalletService
from app.services.apple_wallet_service import AppleWalletService
from app.core.database import AsyncDBSession

logger = logging.getLogger(__name__)

# Router instance
router = APIRouter()

# Initialize services
google_wallet_service = GoogleWalletService()
apple_wallet_service = AppleWalletService()


@router.post("/coupons/generate", response_model=WalletCouponResponse)
async def generate_discount_coupon(
    coupon_request: WalletCouponCreate,
    session: AsyncDBSession,
    current_user: User = Depends(get_current_user),
):
    """Generate a new discount coupon for the authenticated user."""
    try:
        # Generate coupon based on type
        if coupon_request.pass_type.lower() == "google":
            coupon_result = google_wallet_service.generate_coupon_pass(
                current_user.user_id, 
                coupon_request.coupon_data
            )
        elif coupon_request.pass_type.lower() == "apple":
            coupon_result = apple_wallet_service.generate_coupon_pass(
                current_user.user_id, 
                coupon_request.coupon_data
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid wallet type. Must be 'google' or 'apple'"
            )
        
        # Create database record
        wallet_pass = WalletPass(
            user_id=current_user.user_id,
            pass_type=coupon_request.pass_type.lower(),
            pass_class="coupon",
            serial_number=coupon_result["serial_number"],
            pass_data=str(coupon_request.coupon_data),  # Store as JSON string
            pass_url=coupon_result.get("pass_url"),
            expires_at=coupon_request.expires_at or coupon_result.get("expires_at")
        )
        
        session.add(wallet_pass)
        await session.commit()
        await session.refresh(wallet_pass)
        
        logger.info(f"Generated {coupon_request.pass_type} discount coupon for user {current_user.user_id}")
        
        return WalletCouponResponse(
            pass_id=wallet_pass.pass_id,
            user_id=wallet_pass.user_id,
            pass_type=wallet_pass.pass_type,
            pass_class=wallet_pass.pass_class,
            serial_number=wallet_pass.serial_number,
            pass_url=wallet_pass.pass_url,
            is_active=wallet_pass.is_active,
            expires_at=wallet_pass.expires_at,
            created_at=wallet_pass.created_at,
            updated_at=wallet_pass.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to generate discount coupon: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate discount coupon: {str(e)}"
        )


@router.get("/coupons", response_model=CouponListResponse)
async def list_user_coupons(
    session: AsyncDBSession,
    page: int = 1,
    page_size: int = 20,
    pass_type: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """List discount coupons for the authenticated user."""
    try:
        # Build query - only get coupons
        query = select(WalletPass).where(
            WalletPass.user_id == current_user.user_id,
            WalletPass.pass_class == "coupon"
        )
        
        if pass_type:
            query = query.where(WalletPass.pass_type == pass_type.lower())
        
        # Get total count
        count_query = select(WalletPass).where(
            WalletPass.user_id == current_user.user_id,
            WalletPass.pass_class == "coupon"
        )
        if pass_type:
            count_query = count_query.where(WalletPass.pass_type == pass_type.lower())
        
        total_result = await session.exec(count_query)
        total = len(total_result.all())
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        result = await db.exec(query)
        coupons = result.all()
        
        # Convert to response format
        coupon_responses = [
            WalletCouponResponse(
                pass_id=coupon_obj.pass_id,
                user_id=coupon_obj.user_id,
                pass_type=coupon_obj.pass_type,
                pass_class=coupon_obj.pass_class,
                serial_number=coupon_obj.serial_number,
                pass_url=coupon_obj.pass_url,
                is_active=coupon_obj.is_active,
                expires_at=coupon_obj.expires_at,
                created_at=coupon_obj.created_at,
                updated_at=coupon_obj.updated_at
            )
            for coupon_obj in coupons
        ]
        
        return CouponListResponse(
            coupons=coupon_responses,
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to list discount coupons: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve discount coupons"
        )


@router.get("/coupons/{coupon_id}", response_model=WalletCouponResponse)
async def get_discount_coupon(
    session: AsyncDBSession,
    coupon_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific discount coupon by ID."""
    try:
        result = await session.exec(
            select(WalletPass).where(
                WalletPass.pass_id == coupon_id,
                WalletPass.user_id == current_user.user_id,
                WalletPass.pass_class == "coupon"
            )
        )
        wallet_coupon = result.first()
        
        if not wallet_coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount coupon not found"
            )
        
        return WalletCouponResponse(
            pass_id=wallet_coupon.pass_id,
            user_id=wallet_coupon.user_id,
            pass_type=wallet_coupon.pass_type,
            pass_class=wallet_coupon.pass_class,
            serial_number=wallet_coupon.serial_number,
            pass_url=wallet_coupon.pass_url,
            is_active=wallet_coupon.is_active,
            expires_at=wallet_coupon.expires_at,
            created_at=wallet_coupon.created_at,
            updated_at=wallet_coupon.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get discount coupon: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve discount coupon"
        )


@router.get("/coupons/{coupon_id}/download")
async def download_discount_coupon(
    session: AsyncDBSession,
    coupon_id: str,
    # current_user: User = Depends(get_current_user)
):
    """Download a discount coupon file."""
    try:
        # result = await session.exec(
        #     select(WalletPass).where(
        #         WalletPass.pass_id == coupon_id,
        #         WalletPass.user_id == current_user.user_id,
        #         WalletPass.pass_class == "coupon"
        #     )
        # )
        # wallet_coupon = result.first()
        #
        # if not wallet_coupon:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="Discount coupon not found"
        #     )
        
        # if wallet_coupon.pass_type == "apple":
        if True:
            # For Apple Wallet, we need to regenerate the .pkpass file
            # This is a simplified version - in production, you'd store the coupon data
            from app.schemas.wallets import AppleWalletCouponData
            coupon_data = AppleWalletCouponData(
                pass_type_identifier="pass.com.77x.coupon",
                team_identifier="TEAM123456",
                organization_name="77x",
                description="77x Discount Coupon"
            )
            
            pkpass_data = apple_wallet_service.create_coupon_package(coupon_data)
            
            return Response(
                content=pkpass_data,
                media_type="application/vnd.apple.pkpass",
                headers={
                    "Content-Disposition": f"attachment; filename={wallet_coupon.serial_number}.pkpass"
                }
            )
        else:
            # For Google Wallet, redirect to the coupon URL
            if wallet_coupon.pass_url:
                return Response(
                    status_code=status.HTTP_302_FOUND,
                    headers={"Location": wallet_coupon.pass_url}
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Coupon URL not available"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download discount coupon: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download discount coupon"
        )


@router.delete("/coupons/{coupon_id}")
async def delete_discount_coupon(
    session: AsyncDBSession,
    coupon_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a discount coupon."""
    try:
        result = await session.exec(
            select(WalletPass).where(
                WalletPass.pass_id == coupon_id,
                WalletPass.user_id == current_user.user_id,
                WalletPass.pass_class == "coupon"
            )
        )
        wallet_coupon = result.first()
        
        if not wallet_coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Discount coupon not found"
            )
        
        # Mark as inactive instead of deleting
        wallet_coupon.is_active = False
        await session.commit()
        
        logger.info(f"Deactivated discount coupon {coupon_id} for user {current_user.user_id}")
        
        return {"message": "Discount coupon deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete discount coupon: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete discount coupon"
        )


@router.post("/templates", response_model=CouponTemplateResponse)
async def create_coupon_template(
    session: AsyncDBSession,
    template_request: CouponTemplateCreate,
    current_user: User = Depends(get_current_user),
):
    """Create a new discount coupon template."""
    try:
        template = WalletPassTemplate(
            template_name=template_request.template_name,
            pass_type=template_request.pass_type.lower(),
            pass_class="coupon",
            template_data=str(template_request.template_data)
        )
        
        session.add(template)
        await session.commit()
        await session.refresh(template)
        
        logger.info(f"Created discount coupon template: {template_request.template_name}")
        
        return CouponTemplateResponse(
            template_id=template.template_id,
            template_name=template.template_name,
            pass_type=template.pass_type,
            pass_class=template.pass_class,
            template_data=template.template_data,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to create coupon template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create coupon template"
        )


@router.get("/templates", response_model=List[CouponTemplateResponse])
async def list_coupon_templates(
    session: AsyncDBSession,
    pass_type: Optional[str] = None,
):
    """List available discount coupon templates."""
    try:
        query = select(WalletPassTemplate).where(
            WalletPassTemplate.is_active == True,
            WalletPassTemplate.pass_class == "coupon"
        )
        
        if pass_type:
            query = query.where(WalletPassTemplate.pass_type == pass_type.lower())
        
        result = await session.exec(query)
        templates = result.all()
        
        return [
            CouponTemplateResponse(
                template_id=template.template_id,
                template_name=template.template_name,
                pass_type=template.pass_type,
                pass_class=template.pass_class,
                template_data=template.template_data,
                is_active=template.is_active,
                created_at=template.created_at,
                updated_at=template.updated_at
            )
            for template in templates
        ]
        
    except Exception as e:
        logger.error(f"Failed to list coupon templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve coupon templates"
        )
