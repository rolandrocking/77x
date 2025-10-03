"""
SQLModel database models.
"""
import uuid
from sqlmodel import Field
from .base import BaseModel


class User(BaseModel, table=True):
    """User model for the database."""
    __tablename__ = "users"

    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str = Field(index=True, unique=True, max_length=255)
    name: str = Field(max_length=255)
    password_hash: str = Field(max_length=255)

    def __repr__(self):
        return f"<User(id={self.user_id}, email='{self.email}' name='{self.name}')>"
