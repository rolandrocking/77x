"""
SQLModel database models for wallet passes.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import Field, Column, DateTime
from .base import BaseModel


class WalletPass(BaseModel, table=True):
    """Wallet pass model for storing pass data."""
    __tablename__ = "wallet_passes"

    pass_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(index=True, max_length=255)
    pass_type: str = Field(max_length=50)  # 'google' or 'apple'
    pass_class: str = Field(max_length=100)  # e.g., 'coupon', 'loyalty', 'event'
    serial_number: str = Field(unique=True, index=True, max_length=255)
    pass_data: str = Field()  # JSON string containing pass data
    pass_url: Optional[str] = Field(default=None, max_length=500)  # URL to download the pass
    is_active: bool = Field(default=True)
    expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self):
        return f"<WalletPass(id={self.pass_id}, type='{self.pass_type}', serial='{self.serial_number}')>"


class WalletPassTemplate(BaseModel, table=True):
    """Template for wallet pass generation."""
    __tablename__ = "wallet_pass_templates"

    template_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    template_name: str = Field(max_length=100)
    pass_type: str = Field(max_length=50)  # 'google' or 'apple'
    pass_class: str = Field(max_length=100)
    template_data: str = Field()  # JSON string containing template data
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self):
        return f"<WalletPassTemplate(id={self.template_id}, name='{self.template_name}', type='{self.pass_type}')>"
