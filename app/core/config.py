import os
from typing import Optional


class Settings:
    PROJECT_NAME: str = "77x"
    API_SERVICE_STR: str = "/api/v1/"
    debug: bool = True
    
    # Database components
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "coupon_service")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password")
    
    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # JWT configuration
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    
    # Token configuration
    TOKEN_EXPIRY_HOURS: int = int(os.getenv("TOKEN_EXPIRY_HOURS", "24"))
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "77"))
    MAX_TOKENS_PER_USER: int = int(os.getenv("MAX_TOKENS_PER_USER", "1"))
    
    # Redis key constants
    TOKEN_COUNTER_KEY: str = "coupon_token_counter"
    TOKEN_USED_KEY_PREFIX: str = "token_used:"
    USER_COUNTER_KEY_PREFIX: str = "user_token_counter:"
    
    # Google OAuth configuration
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8005/auth/google/callback")
    GOOGLE_SCOPES: str = "openid email profile"
    
    # Google Wallet configuration
    GOOGLE_WALLET_PROJECT_ID: str = os.getenv("GOOGLE_WALLET_PROJECT_ID", "")
    GOOGLE_WALLET_PRIVATE_KEY_ID: str = os.getenv("GOOGLE_WALLET_PRIVATE_KEY_ID", "")
    GOOGLE_WALLET_PRIVATE_KEY: str = os.getenv("GOOGLE_WALLET_PRIVATE_KEY", "")
    GOOGLE_WALLET_CLIENT_EMAIL: str = os.getenv("GOOGLE_WALLET_CLIENT_EMAIL", "")
    GOOGLE_WALLET_CLIENT_ID: str = os.getenv("GOOGLE_WALLET_CLIENT_ID", "")
    GOOGLE_WALLET_ISSUER_ID: str = os.getenv("GOOGLE_WALLET_ISSUER_ID", "")
    GOOGLE_WALLET_ISSUER_NAME: str = os.getenv("GOOGLE_WALLET_ISSUER_NAME", "77x")
    GOOGLE_WALLET_APP_LINK: str = os.getenv("GOOGLE_WALLET_APP_LINK", "https://77x.app")
    
    # Apple Wallet configuration
    APPLE_WALLET_PASS_TYPE_IDENTIFIER: str = os.getenv("APPLE_WALLET_PASS_TYPE_IDENTIFIER", "pass.com.77x.coupon")
    APPLE_WALLET_TEAM_IDENTIFIER: str = os.getenv("APPLE_WALLET_TEAM_IDENTIFIER", "")
    APPLE_WALLET_ORGANIZATION_NAME: str = os.getenv("APPLE_WALLET_ORGANIZATION_NAME", "77x")
    APPLE_WALLET_PRIVATE_KEY_PATH: str = os.getenv("APPLE_WALLET_PRIVATE_KEY_PATH", "")
    APPLE_WALLET_CERTIFICATE_PATH: str = os.getenv("APPLE_WALLET_CERTIFICATE_PATH", "")
    
    # Application configuration
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    @property
    def async_database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# Global settings instance
settings = Settings()
