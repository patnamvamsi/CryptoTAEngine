"""
Structured logging configuration using structlog.
"""
import logging
import sys
from typing import Any
import structlog
from datetime import datetime

from core.config import settings


def setup_logging():
    """
    Configure structured logging for the application.

    Sets up structlog with:
    - JSON formatting for production
    - Console formatting for development
    - Proper log levels
    - Request ID tracking
    """
    # Determine if we should use JSON or console output
    use_json = settings.LOG_FORMAT == "json"

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )

    # Shared processors for all outputs
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    if use_json:
        # JSON output for production
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # Console output for development
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    logger = structlog.get_logger()
    logger.info(
        "logging_configured",
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT
    )


def get_logger(name: str = None) -> Any:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structured logger
    """
    return structlog.get_logger(name)


# Request logging middleware
class LoggingMiddleware:
    """
    Middleware to log HTTP requests and responses.
    """

    def __init__(self, app):
        self.app = app
        self.logger = get_logger(__name__)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request info
        method = scope["method"]
        path = scope["path"]
        client_ip = scope.get("client", ["unknown"])[0]

        # Generate request ID
        request_id = self._generate_request_id()

        # Bind request context
        logger = self.logger.bind(
            request_id=request_id,
            method=method,
            path=path,
            client_ip=client_ip
        )

        start_time = datetime.utcnow()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Log response
                status_code = message["status"]
                duration = (datetime.utcnow() - start_time).total_seconds()

                logger.info(
                    "http_request_completed",
                    status_code=status_code,
                    duration_seconds=duration
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)

    @staticmethod
    def _generate_request_id() -> str:
        """Generate unique request ID."""
        import uuid
        return str(uuid.uuid4())[:8]
