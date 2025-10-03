"""
Pydantic schemas for token-related request/response models.
"""
from pydantic import BaseModel


class TokenValidationRequest(BaseModel):
    """Schema for token validation request."""
    token: str


class TokenUsageRequest(BaseModel):
    """Schema for token usage request."""
    token: str


class TokenResponse(BaseModel):
    """Schema for token response."""
    token: str
    expires_at: str
    token_number: int
    user_id: str
