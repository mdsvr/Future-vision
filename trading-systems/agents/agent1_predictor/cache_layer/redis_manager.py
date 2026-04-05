import json
import logging
import asyncio
from typing import Any

logger = logging.getLogger(__name__)

# Try to import redis, but don't crash if it's missing somehow
try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

class RedisCacheManager:
    """
    Manages caching for heavy API requests.
    Attempts to connect to a local Redis server. If connection fails
    or Redis isn't installed, it gracefully falls back to an in-memory dictionary.
    """
    def __init__(self, host="localhost", port=6379, db=0):
        self._host = host
        self._port = port
        self._cache = {}  # In-memory fallback
        self.use_redis = False
        self.redis_client = None

        if _REDIS_AVAILABLE:
            try:
                # We do not await here because __init__ is synchronous.
                # Connection is established lazily or checked ping down below.
                self.redis_client = aioredis.Redis(host=host, port=port, db=db, decode_responses=True)
                # Note: Testing the connection requires an async ping, which we'll do on first use
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client: {e}. Using in-memory fallback.")
        else:
            logger.warning("redis-py not installed. Using in-memory fallback cache.")

    async def _check_connection(self):
        """Lazily checks if the Redis server is actually alive."""
        if self.redis_client and not self.use_redis:
            try:
                await self.redis_client.ping()
                self.use_redis = True
                logger.info("Connected to Redis successfully.")
            except Exception as e:
                logger.warning(f"Redis is not running on {self._host}:{self._port} ({e}). Falling back to in-memory dict cache.")
                self.redis_client = None

    async def get(self, key: str):
        """Gets a value from cache."""
        await self._check_connection()
        
        if self.use_redis:
            try:
                val = await self.redis_client.get(key)
                return json.loads(val) if val else None
            except Exception as e:
                logger.error(f"Redis GET error: {e}")
                return None
        else:
            # Fallback logic
            item = self._cache.get(key)
            if item:
                # Check expiration
                if item["expires_at"] and asyncio.get_running_loop().time() > item["expires_at"]:
                    del self._cache[key]
                    return None
                return item["value"]
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 60):
        """Sets a value in cache with an expiration time."""
        await self._check_connection()

        if self.use_redis:
            try:
                await self.redis_client.setex(key, ttl_seconds, json.dumps(value))
            except Exception as e:
                logger.error(f"Redis SET error: {e}")
        else:
            # Fallback logic
            expires_at = asyncio.get_running_loop().time() + ttl_seconds if ttl_seconds else None
            self._cache[key] = {"value": value, "expires_at": expires_at}

# Singleton instance
cache = RedisCacheManager()
