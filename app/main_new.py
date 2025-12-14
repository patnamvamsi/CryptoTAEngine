"""
Main FastAPI application with restructured architecture.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import settings
from data.storage.database import db_manager
from data.storage.timeseries import timeseries_db
from utils.cache import redis_cache
from utils.logging_config import setup_logging, LoggingMiddleware
from api.routes import backtest, health, data


# Setup logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting CryptoTA Trading Engine")

    # Initialize database
    try:
        db_manager.initialize()
        db_manager.create_tables()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    # Initialize TimescaleDB
    try:
        timeseries_db.initialize()
        timeseries_db.create_hypertable()
        logger.info("TimescaleDB initialized")
    except Exception as e:
        logger.warning(f"TimescaleDB initialization failed: {e}")

    # Initialize Redis cache
    try:
        redis_cache.connect()
        logger.info("Redis cache connected")
    except Exception as e:
        logger.warning(f"Redis connection failed (cache disabled): {e}")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down CryptoTA Trading Engine")

    try:
        redis_cache.disconnect()
        logger.info("Redis cache disconnected")
    except Exception as e:
        logger.error(f"Error disconnecting Redis: {e}")

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Advanced backtesting and trading engine for cryptocurrencies",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(health.router)
app.include_router(backtest.router)
app.include_router(data.router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_new:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
