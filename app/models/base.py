from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class BaseModel(SQLModel):
    """Base model class with common fields"""
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
