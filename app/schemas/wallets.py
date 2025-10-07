"""
Pydantic schemas for wallet coupon-related request/response models.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class WalletCouponCreate(BaseModel):
    """Schema for creating a wallet coupon."""
    pass_type: str = Field(..., description="Type of wallet: 'google' or 'apple'")
    coupon_data: Dict[str, Any] = Field(..., description="Coupon data including discount information")
    expires_at: Optional[datetime] = Field(None, description="Coupon expiration date")


class WalletCouponResponse(BaseModel):
    """Schema for wallet coupon response."""
    pass_id: str
    user_id: str
    pass_type: str
    pass_class: str
    serial_number: str
    pass_url: Optional[str] = None
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class GoogleWalletCouponData(BaseModel):
    """Schema for Google Wallet coupon data."""
    issuer_id: str = Field(..., description="Google Wallet issuer ID")
    class_id: str = Field(..., description="Google Wallet class ID")
    object_id: str = Field(..., description="Google Wallet object ID")
    card_title: str = Field(..., description="Title displayed on the coupon")
    card_subtitle: Optional[str] = Field(None, description="Subtitle displayed on the coupon")
    card_header: Optional[Dict[str, Any]] = Field(None, description="Header fields")
    card_details: Optional[List[Dict[str, Any]]] = Field(None, description="Detail fields")
    hex_background_color: Optional[str] = Field(None, description="Background color in hex")
    text_modules_data: Optional[List[Dict[str, Any]]] = Field(None, description="Text modules")


class AppleWalletCouponData(BaseModel):
    """Schema for Apple Wallet coupon data."""
    pass_type_identifier: str = Field(..., description="Apple Wallet pass type identifier")
    team_identifier: str = Field(..., description="Apple Developer team identifier")
    organization_name: str = Field(..., description="Organization name")
    description: str = Field(..., description="Coupon description")
    logo_text: Optional[str] = Field(None, description="Logo text")
    foreground_color: Optional[str] = Field(None, description="Foreground color")
    background_color: Optional[str] = Field(None, description="Background color")
    label_color: Optional[str] = Field(None, description="Label color")
    relevant_date: Optional[datetime] = Field(None, description="Relevant date")
    expiration_date: Optional[datetime] = Field(None, description="Expiration date")
    voided: Optional[bool] = Field(False, description="Whether coupon is voided")
    locations: Optional[List[Dict[str, Any]]] = Field(None, description="Location data")
    barcodes: Optional[List[Dict[str, Any]]] = Field(None, description="Barcode data")
    coupon: Optional[Dict[str, Any]] = Field(None, description="Coupon specific data")


class CouponTemplateCreate(BaseModel):
    """Schema for creating a coupon template."""
    template_name: str = Field(..., description="Name of the template")
    pass_type: str = Field(..., description="Type of wallet: 'google' or 'apple'")
    template_data: Dict[str, Any] = Field(..., description="Template data for coupons")


class CouponTemplateResponse(BaseModel):
    """Schema for coupon template response."""
    template_id: str
    template_name: str
    pass_type: str
    pass_class: str
    template_data: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CouponGenerateRequest(BaseModel):
    """Schema for generating a coupon from template."""
    template_id: str = Field(..., description="Template ID to use")
    coupon_data: Dict[str, Any] = Field(..., description="Dynamic data to populate the coupon")
    expires_at: Optional[datetime] = Field(None, description="Coupon expiration date")


class CouponListResponse(BaseModel):
    """Schema for listing wallet coupons."""
    coupons: List[WalletCouponResponse]
    total: int
    page: int
    page_size: int


class DiscountCouponData(BaseModel):
    """Schema for discount coupon data."""
    title: str = Field(..., description="Coupon title")
    discount_percentage: int = Field(..., description="Discount percentage (e.g., 10 for 10%)")
    description: str = Field(..., description="Coupon description")
    terms: Optional[str] = Field(None, description="Terms and conditions")
    background_color: Optional[str] = Field(None, description="Background color")
    foreground_color: Optional[str] = Field(None, description="Foreground color")
    logo_text: Optional[str] = Field(None, description="Logo text")
    expiry_days: Optional[int] = Field(30, description="Days until expiry")
