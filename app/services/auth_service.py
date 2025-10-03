import logging
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:

    @staticmethod
    def hash_password(password: str) -> str:
        # Truncate password to 72 bytes to avoid bcrypt limitation
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        # Truncate password to 72 bytes to match hash_password behavior
        plain_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_auth_token(user_id: str) -> str:
        now = datetime.utcnow()
        payload = {
            "user_id": user_id,
            "type": "auth",
            "issued_at": now.isoformat(),
            "exp": now + timedelta(hours=24)  # 24 hour session
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    @staticmethod
    def generate_coupon_token(token_number: int, user_id: str) -> str:
        now = datetime.utcnow()
        payload = {
            "token_number": token_number,
            "user_id": user_id,
            "issued_at": now.isoformat(),
            "exp": now + timedelta(hours=settings.TOKEN_EXPIRY_HOURS)
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    
    @staticmethod
    def verify_jwt_token(token: str) -> Optional[dict]:

        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT token verification failed: {e}")
            return None
    
    @staticmethod
    def verify_auth_token(token: str) -> Optional[str]:
        """
        Verify and decode an authentication JWT token, return user_id.
        
        Args:
            token: JWT token string
            
        Returns:
            User ID if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("type") == "auth":
                return payload.get("user_id")
            return None
        except jwt.ExpiredSignatureError:
            logger.warning("Auth JWT token has expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"Auth JWT token verification failed: {e}")
            return None
