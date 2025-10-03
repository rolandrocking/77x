"""
Coupon service for token generation and management operations with async Redis.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from fastapi import HTTPException, status

from app.config import settings
from app.services.auth_service import AuthService
from app.redis_manager import redis_manager

logger = logging.getLogger(__name__)


class CouponService:
    """Service for coupon token operations with async Redis."""
    
    def __init__(self):
        self.auth_service = AuthService()
    
    async def check_redis_connection(self) -> bool:
        """
        Check if Redis is available.
        
        Returns:
            True if Redis is connected, False otherwise
        """
        return await redis_manager.ping()
    
    async def generate_coupon(self, current_user_id: str) -> Dict[str, Any]:
        """
        Generate a new coupon token if under the limits.
        Uses atomic Redis operations to prevent race conditions.
        
        Args:
            current_user_id: ID of the user requesting the token
            
        Returns:
            Dictionary containing coupon token information
            
        Raises:
            HTTPException: If limits are exceeded or Redis is unavailable
        """
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
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a coupon token and check if it's been used.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Dictionary containing validation result
        """
        if not await self.check_redis_connection():
            logger.error("Redis connection failed during token validation")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        # Verify JWT token
        payload = self.auth_service.verify_jwt_token(token)
        if not payload:
            return {
                "valid": False,
                "message": "Invalid or expired token"
            }
        
        token_number = payload.get("token_number")
        user_id = payload.get("user_id")
        
        if not token_number or not user_id:
            return {
                "valid": False,
                "message": "Invalid token format"
            }
        
        # Check if token has been used
        used_key = f"{settings.TOKEN_USED_KEY_PREFIX}{token_number}"
        is_used = await redis_manager.exists(used_key)
        
        if is_used:
            return {
                "valid": False,
                "message": "Token has already been used",
                "token_number": token_number,
                "user_id": user_id
            }
        
        return {
            "valid": True,
            "message": "Token is valid and unused",
            "token_number": token_number,
            "user_id": user_id
        }
    
    async def use_token(self, token: str) -> Dict[str, Any]:
        """
        Mark a token as used (single-use enforcement).
        
        Args:
            token: JWT token to mark as used
            
        Returns:
            Dictionary containing usage confirmation
            
        Raises:
            HTTPException: If token is invalid, expired, or already used
        """
        if not await self.check_redis_connection():
            logger.error("Redis connection failed during token usage")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        # Verify JWT token
        payload = self.auth_service.verify_jwt_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )
        
        token_number = payload.get("token_number")
        user_id = payload.get("user_id")
        
        if not token_number or not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token format"
            )
        
        # Check if token has already been used
        used_key = f"{settings.TOKEN_USED_KEY_PREFIX}{token_number}"
        if await redis_manager.exists(used_key):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Token has already been used"
            )
        
        # Mark token as used with expiration
        # Set expiration to match token expiry
        await redis_manager.setex(used_key, settings.TOKEN_EXPIRY_HOURS * 3600, user_id)
        
        logger.info(f"Token #{token_number} for user {user_id} marked as used")
        
        return {
            "message": "Token successfully used",
            "token_number": token_number,
            "user_id": user_id,
            "used_at": datetime.utcnow().isoformat()
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics about token usage.
        
        Returns:
            Dictionary containing usage statistics
            
        Raises:
            HTTPException: If Redis is unavailable
        """
        if not await self.check_redis_connection():
            logger.error("Redis connection failed during stats retrieval")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        try:
            current_count = await redis_manager.get(settings.TOKEN_COUNTER_KEY)
            current_count = int(current_count) if current_count else 0
            
            return {
                "tokens_issued": current_count,
                "tokens_remaining": max(0, settings.MAX_TOKENS - current_count),
                "max_tokens": settings.MAX_TOKENS,
                "max_tokens_per_user": settings.MAX_TOKENS_PER_USER,
                "limit_reached": current_count >= settings.MAX_TOKENS,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Redis error during stats retrieval: {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis error"
            )
    
    async def get_user_stats(self, current_user_id: str) -> Dict[str, Any]:
        """
        Get current user's token statistics.
        
        Args:
            current_user_id: ID of the user
            
        Returns:
            Dictionary containing user's token statistics
            
        Raises:
            HTTPException: If Redis is unavailable
        """
        if not await self.check_redis_connection():
            logger.error("Redis connection failed during user stats retrieval")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        try:
            user_counter_key = f"{settings.USER_COUNTER_KEY_PREFIX}{current_user_id}"
            user_token_count = await redis_manager.get(user_counter_key)
            user_token_count = int(user_token_count) if user_token_count else 0
            
            return {
                "user_id": current_user_id,
                "user_tokens_issued": user_token_count,
                "user_tokens_remaining": max(0, settings.MAX_TOKENS_PER_USER - user_token_count),
                "max_tokens_per_user": settings.MAX_TOKENS_PER_USER,
                "user_limit_reached": user_token_count >= settings.MAX_TOKENS_PER_USER,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Redis error during user stats retrieval: {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis error"
            )
