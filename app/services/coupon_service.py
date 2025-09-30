"""
Coupon service for token generation and management operations.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

import redis

from app.config import settings
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class CouponService:
    """Service for coupon token operations."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.auth_service = AuthService()
    
    def check_redis_connection(self) -> bool:
        """
        Check if Redis is available.
        
        Returns:
            True if Redis is connected, False otherwise
        """
        try:
            self.redis_client.ping()
            return True
        except redis.RedisError:
            return False
    
    def generate_coupon(self, current_user_id: str) -> Dict[str, Any]:
        """
        Generate a new coupon token if under the limits.
        
        Args:
            current_user_id: ID of the user requesting the token
            
        Returns:
            Dictionary containing coupon token information
            
        Raises:
            HTTPException: If limits are exceeded or Redis is unavailable
        """
        if not self.check_redis_connection():
            logger.error("Redis connection failed during coupon generation")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        try:
            # Check user's token count first
            user_counter_key = f"{settings.USER_COUNTER_KEY_PREFIX}{current_user_id}"
            user_token_count = self.redis_client.incr(user_counter_key)
            
            if user_token_count > settings.MAX_TOKENS_PER_USER:
                # Decrement back since user can't have more tokens
                self.redis_client.decr(user_counter_key)
                logger.warning(f"User {current_user_id} token limit reached. Attempted to issue token #{user_token_count}")
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"User token limit reached. Maximum of {settings.MAX_TOKENS_PER_USER} tokens per user allowed."
                )
            
            # Check global token limit
            global_count = self.redis_client.incr(settings.TOKEN_COUNTER_KEY)
            
            if global_count > settings.MAX_TOKENS:
                # Decrement both counters since we can't issue the token
                self.redis_client.decr(settings.TOKEN_COUNTER_KEY)
                self.redis_client.decr(user_counter_key)
                remaining = settings.MAX_TOKENS - (global_count - 1)
                
                logger.warning(f"Global token limit reached. Attempted to issue token #{global_count}")
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Global token limit reached. Maximum of {settings.MAX_TOKENS} tokens allowed. {remaining} tokens remaining."
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
            
        except redis.RedisError as e:
            logger.error(f"Redis error during coupon generation: {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis error"
            )
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a coupon token and check if it's been used.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Dictionary containing validation result
        """
        if not self.check_redis_connection():
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
        is_used = self.redis_client.exists(used_key)
        
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
    
    def use_token(self, token: str) -> Dict[str, Any]:
        """
        Mark a token as used (single-use enforcement).
        
        Args:
            token: JWT token to mark as used
            
        Returns:
            Dictionary containing usage confirmation
            
        Raises:
            HTTPException: If token is invalid, expired, or already used
        """
        if not self.check_redis_connection():
            logger.error("Redis connection failed during token usage")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        # Verify JWT token
        payload = self.auth_service.verify_jwt_token(token)
        if not payload:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )
        
        token_number = payload.get("token_number")
        user_id = payload.get("user_id")
        
        if not token_number or not user_id:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token format"
            )
        
        # Check if token has already been used
        used_key = f"{settings.TOKEN_USED_KEY_PREFIX}{token_number}"
        if self.redis_client.exists(used_key):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Token has already been used"
            )
        
        # Mark token as used with expiration
        # Set expiration to match token expiry
        self.redis_client.setex(used_key, settings.TOKEN_EXPIRY_HOURS * 3600, user_id)
        
        logger.info(f"Token #{token_number} for user {user_id} marked as used")
        
        return {
            "message": "Token successfully used",
            "token_number": token_number,
            "user_id": user_id,
            "used_at": datetime.utcnow().isoformat()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get current statistics about token usage.
        
        Returns:
            Dictionary containing usage statistics
            
        Raises:
            HTTPException: If Redis is unavailable
        """
        if not self.check_redis_connection():
            logger.error("Redis connection failed during stats retrieval")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        try:
            current_count = self.redis_client.get(settings.TOKEN_COUNTER_KEY)
            current_count = int(current_count) if current_count else 0
            
            return {
                "tokens_issued": current_count,
                "tokens_remaining": max(0, settings.MAX_TOKENS - current_count),
                "max_tokens": settings.MAX_TOKENS,
                "max_tokens_per_user": settings.MAX_TOKENS_PER_USER,
                "limit_reached": current_count >= settings.MAX_TOKENS,
                "timestamp": datetime.utcnow().isoformat()
            }
        except redis.RedisError as e:
            logger.error(f"Redis error during stats retrieval: {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis error"
            )
    
    def get_user_stats(self, current_user_id: str) -> Dict[str, Any]:
        """
        Get current user's token statistics.
        
        Args:
            current_user_id: ID of the user
            
        Returns:
            Dictionary containing user's token statistics
            
        Raises:
            HTTPException: If Redis is unavailable
        """
        if not self.check_redis_connection():
            logger.error("Redis connection failed during user stats retrieval")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis connection failed"
            )
        
        try:
            user_counter_key = f"{settings.USER_COUNTER_KEY_PREFIX}{current_user_id}"
            user_token_count = self.redis_client.get(user_counter_key)
            user_token_count = int(user_token_count) if user_token_count else 0
            
            return {
                "user_id": current_user_id,
                "user_tokens_issued": user_token_count,
                "user_tokens_remaining": max(0, settings.MAX_TOKENS_PER_USER - user_token_count),
                "max_tokens_per_user": settings.MAX_TOKENS_PER_USER,
                "user_limit_reached": user_token_count >= settings.MAX_TOKENS_PER_USER,
                "timestamp": datetime.utcnow().isoformat()
            }
        except redis.RedisError as e:
            logger.error(f"Redis error during user stats retrieval: {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service temporarily unavailable - Redis error"
            )
