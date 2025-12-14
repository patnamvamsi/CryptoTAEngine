"""
FastAPI dependencies for dependency injection.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Generator

from data.storage.database import db_manager
from utils.cache import redis_cache, backtest_cache
from backtesting.engine import BacktestEngine
from data.providers.binance_provider import BinanceDataProvider
from core.config import settings


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.

    Yields:
        Database session
    """
    return db_manager.get_db()


def get_cache():
    """
    Get Redis cache instance.

    Returns:
        RedisCache instance
    """
    if not redis_cache.client:
        try:
            redis_cache.connect()
        except Exception:
            # Return None if Redis is unavailable
            return None

    return redis_cache


def get_backtest_cache():
    """
    Get backtest cache instance.

    Returns:
        BacktestCache instance
    """
    return backtest_cache


def get_backtest_engine():
    """
    Get backtesting engine.

    Returns:
        BacktestEngine instance
    """
    return BacktestEngine()


def get_data_provider():
    """
    Get Binance data provider.

    Returns:
        BinanceDataProvider instance
    """
    return BinanceDataProvider()


def verify_api_key(api_key: str = None) -> bool:
    """
    Verify API key for protected endpoints (if needed).

    Args:
        api_key: API key from request header

    Returns:
        True if valid

    Raises:
        HTTPException if invalid
    """
    # Implement API key verification if needed
    # For now, just return True
    return True


class RateLimiter:
    """Simple rate limiter using Redis."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check_rate_limit(self, identifier: str, cache=Depends(get_cache)) -> bool:
        """
        Check if request is within rate limit.

        Args:
            identifier: Unique identifier (e.g., IP address)
            cache: Redis cache instance

        Returns:
            True if within limit

        Raises:
            HTTPException if rate limit exceeded
        """
        if cache is None:
            # If Redis is unavailable, allow request
            return True

        key = f"rate_limit:{identifier}"

        # Get current count
        current = cache.get(key) or 0

        if current >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds} seconds."
            )

        # Increment counter
        if current == 0:
            cache.set(key, 1, ttl=self.window_seconds)
        else:
            cache.increment(key)

        return True
