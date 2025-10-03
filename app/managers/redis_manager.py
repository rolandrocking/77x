import logging
import asyncio
from typing import Optional, Any
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)


class AsyncRedisManager:
    
    def __init__(self):
        self.pool: Optional[ConnectionPool] = None
        self.redis: Optional[redis.Redis] = None
        self._connection_lock = asyncio.Lock()
    
    async def initialize(self):
        async with self._connection_lock:
            if self.pool is None:
                try:
                    # Create connection pool with optimized settings
                    self.pool = ConnectionPool(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        db=settings.REDIS_DB,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        max_connections=20,  # Connection pool size
                        health_check_interval=30,  # Health check every 30 seconds
                    )
                    
                    # Create Redis client with the pool
                    self.redis = redis.Redis(connection_pool=self.pool)
                    
                    # Test connection
                    await self.redis.ping()
                    logger.info("Redis connection pool initialized successfully")
                    
                except Exception as e:
                    logger.error(f"Failed to initialize Redis connection pool: {e}")
                    raise
    
    async def close(self):
        """Close Redis connection pool."""
        async with self._connection_lock:
            if self.redis:
                await self.redis.close()
                self.redis = None
            if self.pool:
                await self.pool.disconnect()
                self.pool = None
            logger.info("Redis connection pool closed")
    
    async def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            if not self.redis:
                await self.initialize()
            await self.redis.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
            return False
    
    async def atomic_increment_with_limit(
        self, 
        key: str, 
        limit: int, 
        rollback_keys: Optional[list] = None
    ) -> tuple[int, bool]:

        if not self.redis:
            await self.initialize()
        
        # Use Redis pipeline for atomic operations
        async with self.redis.pipeline() as pipe:
            try:
                # Start watching the key for changes
                await pipe.watch(key)
                
                # Get current value
                current_value = await pipe.get(key)
                current_value = int(current_value) if current_value else 0
                
                # Check if we can increment
                if current_value >= limit:
                    await pipe.unwatch()
                    return current_value, False
                
                # Start transaction
                pipe.multi()
                
                # Increment the counter
                pipe.incr(key)
                
                # Execute the transaction
                result = await pipe.execute()
                new_value = result[0]
                
                # Double-check the limit after increment
                if new_value > limit:
                    # Rollback: decrement the counter
                    await self.redis.decr(key)
                    
                    # Rollback other keys if provided
                    if rollback_keys:
                        for rollback_key in rollback_keys:
                            await self.redis.decr(rollback_key)
                    
                    return new_value - 1, False
                
                return new_value, True
                
            except redis.WatchError:
                # Another client modified the key, retry
                logger.warning(f"Redis watch error for key {key}, retrying...")
                await asyncio.sleep(0.01)  # Small delay before retry
                return await self.atomic_increment_with_limit(key, limit, rollback_keys)
            except Exception as e:
                logger.error(f"Redis atomic operation failed: {e}")
                raise
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        if not self.redis:
            await self.initialize()
        return await self.redis.get(key)
    
    async def set(self, key: str, value: Any) -> bool:
        """Set value in Redis."""
        if not self.redis:
            await self.initialize()
        return await self.redis.set(key, value)
    
    async def setex(self, key: str, time: int, value: Any) -> bool:
        """Set value with expiration in Redis."""
        if not self.redis:
            await self.initialize()
        return await self.redis.setex(key, time, value)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.redis:
            await self.initialize()
        return await self.redis.exists(key)
    
    async def delete(self, *keys: str) -> int:
        """Delete keys from Redis."""
        if not self.redis:
            await self.initialize()
        return await self.redis.delete(*keys)
    
    async def scan_iter(self, match: str = "*", count: int = 100):
        """Scan Redis keys with pattern matching."""
        if not self.redis:
            await self.initialize()
        async for key in self.redis.scan_iter(match=match, count=count):
            yield key


# Global Redis manager instance
redis_manager = AsyncRedisManager()


@asynccontextmanager
async def get_redis():
    """Context manager for Redis operations."""
    if not redis_manager.redis:
        await redis_manager.initialize()
    yield redis_manager

