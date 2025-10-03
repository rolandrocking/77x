import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import HTTPException, status

from app.core.config import settings
from app.services.auth_service import AuthService
from app.managers.redis_manager import redis_manager

logger = logging.getLogger(__name__)


class CouponService:
    """Service for coupon token operations with async Redis."""
    
    def __init__(self):
        self.auth_service = AuthService()
    
    async def check_redis_connection(self) -> bool:
        return await redis_manager.ping()
    
    async def generate_coupon(self, current_user_id: str) -> Dict[str, Any]:
        if not await self.check_redis_connection():
            logger.error("Redis connection failed during coupon generation")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        try:
            # Check user's token count first with atomic operation
            user_counter_key = f"{settings.USER_COUNTER_KEY_PREFIX}{current_user_id}"
            user_token_count, user_success = await redis_manager.atomic_increment_with_limit(
                user_counter_key, 
                settings.MAX_TOKENS_PER_USER
            )
            
            if not user_success:
                logger.warning(f"User {current_user_id} token limit reached. Attempted to issue token #{user_token_count}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"User token limit reached. Maximum of {settings.MAX_TOKENS_PER_USER} tokens per user allowed."
                )
            
            # Check global token limit with atomic operation
            global_count, global_success = await redis_manager.atomic_increment_with_limit(
                settings.TOKEN_COUNTER_KEY,
                settings.MAX_TOKENS,
                rollback_keys=[user_counter_key]  # Rollback user counter if global limit exceeded
            )
            
            if not global_success:
                logger.warning(f"Global token limit reached. Attempted to issue token #{global_count}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Global token limit reached. Maximum of {settings.MAX_TOKENS} tokens allowed. {settings.MAX_TOKENS - global_count} tokens remaining."
                )
            
            # Generate the token
            token = self.auth_service.generate_coupon_token(global_count, current_user_id)
            expires_at = datetime.utcnow() + timedelta(hours=settings.TOKEN_EXPIRY_HOURS)
            remaining_tokens = settings.MAX_TOKENS - global_count
            
            logger.info(f"Generated token #{global_count} for user {current_user_id}. {remaining_tokens} global tokens remaining.")
            
            return {
                "token": token,
                "expires_at": expires_at,
                "token_number": global_count,
                "remaining_tokens": remaining_tokens,
                "user_id": current_user_id
            }
            
        except Exception as e:
            logger.error(f"Redis error during coupon generation: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis error"
            )
