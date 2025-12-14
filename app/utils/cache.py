"""
Redis caching layer for backtest results and data.
"""
import redis
import pickle
import json
import hashlib
from typing import Any, Optional
from datetime import timedelta
import logging

from core.config import settings
from core.exceptions import CacheError

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis-based caching with automatic serialization."""

    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = None):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL (uses settings if not provided)
            default_ttl: Default time-to-live in seconds
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.default_ttl = default_ttl or settings.CACHE_TTL
        self.client = None

    def connect(self):
        """Establish Redis connection."""
        try:
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_keepalive=True
            )

            # Test connection
            self.client.ping()
            logger.info("Redis cache connected successfully")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise CacheError(f"Redis connection failed: {e}")

    def disconnect(self):
        """Close Redis connection."""
        if self.client:
            self.client.close()
            logger.info("Redis cache disconnected")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self.client:
            self.connect()

        try:
            cached = self.client.get(key)
            if cached:
                logger.debug(f"Cache hit: {key}")
                return pickle.loads(cached)

            logger.debug(f"Cache miss: {key}")
            return None

        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be pickled)
            ttl: Time-to-live in seconds (uses default if not provided)
            nx: Only set if key does NOT exist
            xx: Only set if key DOES exist

        Returns:
            True if successful
        """
        if not self.client:
            self.connect()

        try:
            ttl = ttl or self.default_ttl
            pickled_value = pickle.dumps(value)

            result = self.client.set(
                key,
                pickled_value,
                ex=ttl,
                nx=nx,
                xx=xx
            )

            if result:
                logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

            return bool(result)

        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted
        """
        if not self.client:
            self.connect()

        try:
            result = self.client.delete(key)
            logger.debug(f"Cache delete: {key}")
            return bool(result)

        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.client:
            self.connect()

        try:
            return bool(self.client.exists(key))

        except Exception as e:
            logger.error(f"Cache exists error for {key}: {e}")
            return False

    def get_ttl(self, key: str) -> int:
        """
        Get remaining TTL for a key.

        Returns:
            TTL in seconds, -1 if no expiry, -2 if key doesn't exist
        """
        if not self.client:
            self.connect()

        try:
            return self.client.ttl(key)

        except Exception as e:
            logger.error(f"Cache TTL error for {key}: {e}")
            return -2

    def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a counter.

        Args:
            key: Cache key
            amount: Amount to increment

        Returns:
            New value
        """
        if not self.client:
            self.connect()

        try:
            return self.client.incrby(key, amount)

        except Exception as e:
            logger.error(f"Cache increment error for {key}: {e}")
            return 0

    def clear_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "backtest:*")

        Returns:
            Number of keys deleted
        """
        if not self.client:
            self.connect()

        try:
            keys = self.client.keys(pattern)
            if keys:
                deleted = self.client.delete(*keys)
                logger.info(f"Deleted {deleted} keys matching {pattern}")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0

    def flush_all(self):
        """Delete all keys (use with caution!)."""
        if not self.client:
            self.connect()

        try:
            self.client.flushdb()
            logger.warning("Cache flushed (all keys deleted)")

        except Exception as e:
            logger.error(f"Cache flush error: {e}")


class BacktestCache:
    """Specialized cache for backtest results."""

    def __init__(self, redis_cache: Optional[RedisCache] = None):
        """Initialize backtest cache."""
        self.cache = redis_cache or RedisCache()

    @staticmethod
    def generate_cache_key(
        strategy: str,
        symbol: str,
        start_date: str,
        end_date: str,
        parameters: dict
    ) -> str:
        """
        Generate deterministic cache key for backtest.

        Args:
            strategy: Strategy name
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            parameters: Strategy parameters

        Returns:
            Cache key
        """
        # Sort parameters for consistent hashing
        param_str = json.dumps(parameters, sort_keys=True)

        # Create hash of all inputs
        key_data = f"{strategy}:{symbol}:{start_date}:{end_date}:{param_str}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()

        return f"backtest:{strategy}:{symbol}:{key_hash}"

    def get_cached_backtest(
        self,
        strategy: str,
        symbol: str,
        start_date: str,
        end_date: str,
        parameters: dict
    ) -> Optional[dict]:
        """
        Get cached backtest result.

        Args:
            strategy: Strategy name
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            parameters: Strategy parameters

        Returns:
            Cached result or None
        """
        key = self.generate_cache_key(strategy, symbol, start_date, end_date, parameters)
        result = self.cache.get(key)

        if result:
            logger.info(f"Backtest cache hit for {strategy} {symbol}")

        return result

    def cache_backtest_result(
        self,
        strategy: str,
        symbol: str,
        start_date: str,
        end_date: str,
        parameters: dict,
        result: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache backtest result.

        Args:
            strategy: Strategy name
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            parameters: Strategy parameters
            result: Backtest result to cache
            ttl: Time-to-live (optional)

        Returns:
            True if cached successfully
        """
        key = self.generate_cache_key(strategy, symbol, start_date, end_date, parameters)
        success = self.cache.set(key, result, ttl=ttl)

        if success:
            logger.info(f"Cached backtest result for {strategy} {symbol}")

        return success

    def invalidate_symbol(self, symbol: str):
        """Invalidate all cached backtests for a symbol."""
        pattern = f"backtest:*:{symbol}:*"
        deleted = self.cache.clear_pattern(pattern)
        logger.info(f"Invalidated {deleted} cached backtests for {symbol}")


# Global cache instances
redis_cache = RedisCache()
backtest_cache = BacktestCache(redis_cache)
