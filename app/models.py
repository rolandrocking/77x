"""
Pydantic models for request/response schemas.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    """Schema for user registration request."""
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    user_id: str
    email: str
    name: str
    created_at: datetime


class AuthResponse(BaseModel):
    """Schema for authentication response."""
    access_token: str
    token_type: str
    user: UserResponse


class CouponResponse(BaseModel):
    """Schema for coupon generation response."""
    token: str
    expires_at: datetime
    token_number: int
    remaining_tokens: int
    user_id: str


class ErrorResponse(BaseModel):
    """Schema for error response."""
    error: str
    message: str
    remaining_tokens: int


class TokenValidationResponse(BaseModel):
    """Schema for token validation response."""
    valid: bool
    message: str
    token_number: Optional[int] = None
    user_id: Optional[str] = None


class StatsResponse(BaseModel):
    """Schema for statistics response."""
    tokens_issued: int
    tokens_remaining: int
    max_tokens: int
    max_tokens_per_user: int
    limit_reached: bool
    timestamp: datetime


class UserStatsResponse(BaseModel):
    """Schema for user statistics response."""
    user_id: str
    user_tokens_issued: int
    user_tokens_remaining: int
    max_tokens_per_user: int
    user_limit_reached: bool
    timestamp: datetime


class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    redis_connected: bool
    timestamp: datetime


class TokenUsageResponse(BaseModel):
    """Schema for token usage response."""
    message: str
    token_number: int
    user_id: str
    used_at: datetime


class GoogleUserInfo(BaseModel):
    """Schema for Google user information."""
    google_id: str
    name: str
    email: str
    picture: str


class GoogleAuthResponse(BaseModel):
    """Schema for Google OAuth authentication response."""
    access_token: str
    token_type: str
    google_user_info: GoogleUserInfo
    message: str
