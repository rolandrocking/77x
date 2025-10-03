"""
SQLAlchemy database models.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID
import uuid


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class User(Base):
    """User model for the database."""
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.user_id}, email='{self.email}' name='{self.name}')>"

# Future database models can be added here
# class Coupon(Base):
#     __tablename__ = "coupons"
#     # ... fields