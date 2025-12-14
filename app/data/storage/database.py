"""
Database models and connection management using SQLAlchemy.
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, JSON, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from typing import Generator
from contextlib import contextmanager
import logging

from core.config import settings

logger = logging.getLogger(__name__)

# Create base class for declarative models
Base = declarative_base()


# Database Models
class BacktestRun(Base):
    """Store backtest execution results."""
    __tablename__ = 'backtest_runs'

    id = Column(String, primary_key=True)
    strategy = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    timeframe = Column(String, nullable=False)

    # Configuration
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float)
    commission = Column(Float)
    parameters = Column(JSON)  # Strategy parameters

    # Performance Metrics
    total_return = Column(Float)
    annual_return = Column(Float)
    cagr = Column(Float)
    volatility = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    calmar_ratio = Column(Float)

    # Trading Metrics
    total_trades = Column(Integer)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    avg_win = Column(Float)
    avg_loss = Column(Float)
    avg_trade = Column(Float)

    # Execution Info
    status = Column(String, nullable=False, default='submitted')  # submitted, running, completed, failed
    execution_time = Column(Float)  # seconds
    error_message = Column(String)

    # Full results stored as JSON
    full_results = Column(JSON)  # Contains trades, equity curve, etc.

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_strategy_symbol', 'strategy', 'symbol'),
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )


class OptimizationRun(Base):
    """Store parameter optimization results."""
    __tablename__ = 'optimization_runs'

    id = Column(String, primary_key=True)
    strategy = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Optimization configuration
    parameter_grid = Column(JSON)  # Parameters being optimized
    optimization_metric = Column(String)  # Metric being optimized (e.g., sharpe_ratio)

    # Results
    best_parameters = Column(JSON)
    best_metric_value = Column(Float)
    total_combinations = Column(Integer)
    completed_combinations = Column(Integer)

    # All results
    all_results = Column(JSON)  # List of all parameter combinations and their metrics

    # Execution
    status = Column(String, nullable=False, default='submitted')
    execution_time = Column(Float)
    error_message = Column(String)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LiveTrade(Base):
    """Store live trading execution records."""
    __tablename__ = 'live_trades'

    id = Column(String, primary_key=True)
    strategy = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    # Order details
    order_id = Column(String, unique=True)
    side = Column(String, nullable=False)  # BUY or SELL
    order_type = Column(String)  # MARKET, LIMIT, etc.

    # Execution
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    quantity = Column(Float, nullable=False)

    # P&L
    pnl = Column(Float)
    pnl_percent = Column(Float)
    commission = Column(Float)

    # Status
    status = Column(String, nullable=False)  # OPEN, CLOSED, CANCELLED

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_strategy_status', 'strategy', 'status'),
        Index('idx_entry_time', 'entry_time'),
    )


class DataCache(Base):
    """Cache for historical market data."""
    __tablename__ = 'data_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    timeframe = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Data location or reference
    data_path = Column(String)  # Path to CSV or parquet file
    record_count = Column(Integer)

    # Cache metadata
    is_valid = Column(Boolean, default=True)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Composite index for lookups
    __table_args__ = (
        Index('idx_symbol_timeframe_dates', 'symbol', 'timeframe', 'start_date', 'end_date'),
    )


# Database connection management
class DatabaseManager:
    """Manage database connections and sessions."""

    def __init__(self, database_url: str = None):
        """Initialize database manager."""
        self.database_url = database_url or settings.DATABASE_URL
        self.engine = None
        self.SessionLocal = None

    def initialize(self):
        """Create database engine and session factory."""
        logger.info(f"Initializing database connection")

        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
            echo=settings.DEBUG  # Log SQL in debug mode
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info("Database connection initialized")

    def create_tables(self):
        """Create all tables if they don't exist."""
        if self.engine is None:
            self.initialize()

        logger.info("Creating database tables")
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")

    def drop_tables(self):
        """Drop all tables (use with caution!)."""
        if self.engine is None:
            self.initialize()

        logger.warning("Dropping all database tables")
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session with automatic cleanup.

        Usage:
            with db_manager.get_session() as session:
                # Use session
                session.query(...)
        """
        if self.SessionLocal is None:
            self.initialize()

        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def get_db(self) -> Generator[Session, None, None]:
        """
        Dependency for FastAPI endpoints.

        Usage:
            @app.get("/endpoint")
            def endpoint(db: Session = Depends(db_manager.get_db)):
                # Use db
        """
        if self.SessionLocal is None:
            self.initialize()

        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()


# Global database manager instance
db_manager = DatabaseManager()


# Convenience function for getting a session
def get_db() -> Generator[Session, None, None]:
    """Get database session (for FastAPI dependency injection)."""
    return db_manager.get_db()
