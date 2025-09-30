"""
Configuration settings for the application.
"""
import os
from typing import Optional


class Settings:
    """Application configuration settings."""
    
    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # JWT configuration
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    
    # Token configuration
    TOKEN_EXPIRY_HOURS: int = 24
    MAX_TOKENS: int = 77
    MAX_TOKENS_PER_USER: int = 5
    
    # Database configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:password@localhost:5432/coupon_service"
    )
    
    # Redis key constants
    TOKEN_COUNTER_KEY: str = "coupon_token_counter"
    TOKEN_USED_KEY_PREFIX: str = "token_used:"
    USER_COUNTER_KEY_PREFIX: str = "user_token_counter:"


# Global settings instance
settings = Settings()
