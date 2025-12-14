"""
Health check and system status routes.
"""
from fastapi import APIRouter, Depends
from datetime import datetime
import logging

from core.models import HealthResponse
from core.config import settings
from api.dependencies import get_cache, get_db
from data.storage.database import db_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse)
async def health_check(
    cache=Depends(get_cache),
    db=Depends(get_db)
):
    """
    Health check endpoint.

    Returns system status and service availability.
    """
    services = {}

    # Check database
    try:
        # Simple query to test database connection
        next(db_manager.get_db())
        services['database'] = 'healthy'
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        services['database'] = 'unhealthy'

    # Check Redis cache
    if cache:
        try:
            cache.client.ping()
            services['cache'] = 'healthy'
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            services['cache'] = 'unhealthy'
    else:
        services['cache'] = 'unavailable'

    # Overall status
    overall_status = 'healthy' if all(
        s in ['healthy', 'unavailable'] for s in services.values()
    ) else 'degraded'

    return HealthResponse(
        status=overall_status,
        version=settings.API_VERSION,
        timestamp=datetime.utcnow(),
        services=services
    )


@router.get("/ping")
async def ping():
    """Simple ping endpoint."""
    return {"status": "ok", "message": "pong"}
