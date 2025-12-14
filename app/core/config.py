"""
Configuration management using Pydantic Settings.
Loads settings from environment variables or .env file.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    API_TITLE: str = "CryptoTA Trading Engine"
    API_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Binance API
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET: bool = True
    BINANCE_TESTNET_URL: str = "https://testnet.binance.vision/api"

    # Data Storage
    DATA_DIR: str = "/data"
    CACHE_DIR: str = "/cache"
    BACKTEST_DATA_PATH: str = "/data/2020_15minutes.csv"

    # TimescaleDB Configuration (shared with CryptoMarketData microservice)
    TIMESCALE_USER: str = "postgres"
    TIMESCALE_PASSWORD: str = "postgres"
    TIMESCALE_HOST: str = "localhost"
    TIMESCALE_PORT: int = 5432
    TIMESCALE_DB: str = "market_data"  # Shared database with CryptoMarketData

    @property
    def DATABASE_URL(self) -> str:
        """
        Construct database URL from components.
        Uses TimescaleDB for both regular tables and time series data.
        """
        return f"postgresql://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"

    @property
    def TIMESCALE_URL(self) -> str:
        """Alias for DATABASE_URL - same database handles both."""
        return self.DATABASE_URL

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    CACHE_TTL: int = 86400  # 24 hours

    @property
    def REDIS_URL(self) -> str:
        """Construct Redis URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Celery Configuration
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    @property
    def CELERY_BROKER(self) -> str:
        """Celery broker URL, defaults to Redis."""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def CELERY_BACKEND(self) -> str:
        """Celery result backend, defaults to Redis."""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    # Backtesting Configuration
    INITIAL_CAPITAL: float = 10000.0
    COMMISSION: float = 0.001  # 0.1%
    SLIPPAGE: float = 0.0005   # 0.05%

    # Trading Configuration
    MAX_POSITION_SIZE: float = 0.1  # 10% of capital per position
    RISK_PER_TRADE: float = 0.02    # 2% risk per trade

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # or "console"

    # Performance
    WORKERS: int = 4
    MAX_PARALLEL_BACKTESTS: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded only once.
    """
    return Settings()


# Convenience exports
settings = get_settings()
