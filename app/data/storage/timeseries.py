"""
TimescaleDB integration for efficient time series data storage.
"""
from sqlalchemy import create_engine, Column, String, Float, DateTime, BigInteger, Index, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
import logging

from core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class OHLCV(Base):
    """
    OHLCV (Open, High, Low, Close, Volume) candlestick data.
    Optimized for TimescaleDB hypertable.
    """
    __tablename__ = 'ohlcv'

    time = Column(DateTime, primary_key=True, nullable=False)
    symbol = Column(String, primary_key=True, nullable=False)
    timeframe = Column(String, nullable=False)

    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

    # Additional metrics
    trades = Column(BigInteger)  # Number of trades
    quote_volume = Column(Float)  # Volume in quote asset

    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_symbol_time', 'symbol', 'time'),
        Index('idx_timeframe', 'timeframe'),
    )


class TimeSeriesDB:
    """Manage TimescaleDB connections and operations."""

    def __init__(self, database_url: str = None):
        """Initialize TimescaleDB manager."""
        self.database_url = database_url or settings.TIMESCALE_URL
        self.engine = None
        self.SessionLocal = None

    def initialize(self):
        """Create database engine and enable TimescaleDB."""
        logger.info("Initializing TimescaleDB connection")

        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=settings.DEBUG
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info("TimescaleDB connection initialized")

    def create_hypertable(self):
        """Create OHLCV table as TimescaleDB hypertable."""
        if self.engine is None:
            self.initialize()

        # Create table
        Base.metadata.create_all(bind=self.engine)

        # Convert to hypertable
        with self.engine.connect() as conn:
            try:
                # Check if already a hypertable
                result = conn.execute(text(
                    "SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'ohlcv'"
                ))

                if result.fetchone() is None:
                    # Create hypertable
                    conn.execute(text(
                        "SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE, "
                        "partitioning_column => 'symbol', number_partitions => 4)"
                    ))
                    conn.commit()
                    logger.info("Created OHLCV hypertable")
                else:
                    logger.info("OHLCV hypertable already exists")

            except Exception as e:
                logger.error(f"Error creating hypertable: {e}")
                # Continue even if hypertable creation fails (regular table will work)

    def insert_ohlcv(self, data: pd.DataFrame, symbol: str, timeframe: str):
        """
        Insert OHLCV data into TimescaleDB.

        Args:
            data: DataFrame with columns [timestamp, open, high, low, close, volume]
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '15m', '1h')
        """
        if self.SessionLocal is None:
            self.initialize()

        # Prepare data
        data = data.copy()
        data['symbol'] = symbol
        data['timeframe'] = timeframe

        # Rename columns to match database
        column_mapping = {
            'timestamp': 'time',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }

        data = data.rename(columns=column_mapping)

        # Convert timestamp to datetime if needed
        if 'time' in data.columns:
            data['time'] = pd.to_datetime(data['time'])

        # Insert using pandas to_sql
        data.to_sql(
            'ohlcv',
            self.engine,
            if_exists='append',
            index=False,
            method='multi',  # Batch insert
            chunksize=1000
        )

        logger.info(f"Inserted {len(data)} rows for {symbol} {timeframe}")

    def query_ohlcv(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = '15m'
    ) -> pd.DataFrame:
        """
        Query OHLCV data from TimescaleDB.

        Args:
            symbol: Trading symbol
            start_date: Start datetime
            end_date: End datetime
            timeframe: Timeframe

        Returns:
            DataFrame with OHLCV data
        """
        if self.engine is None:
            self.initialize()

        query = text("""
            SELECT time, open, high, low, close, volume, trades, quote_volume
            FROM ohlcv
            WHERE symbol = :symbol
                AND timeframe = :timeframe
                AND time >= :start_date
                AND time <= :end_date
            ORDER BY time ASC
        """)

        df = pd.read_sql(
            query,
            self.engine,
            params={
                'symbol': symbol,
                'timeframe': timeframe,
                'start_date': start_date,
                'end_date': end_date
            }
        )

        return df

    def get_latest_timestamp(self, symbol: str, timeframe: str) -> datetime:
        """Get the latest timestamp for a symbol/timeframe."""
        if self.SessionLocal is None:
            self.initialize()

        with self.SessionLocal() as session:
            result = session.execute(
                text(
                    "SELECT MAX(time) as latest FROM ohlcv "
                    "WHERE symbol = :symbol AND timeframe = :timeframe"
                ),
                {'symbol': symbol, 'timeframe': timeframe}
            ).fetchone()

            return result[0] if result and result[0] else None

    def create_continuous_aggregate(self, source_timeframe: str, target_timeframe: str):
        """
        Create continuous aggregate for downsampling data.

        Example: Create 1h view from 15m data
        """
        if self.engine is None:
            self.initialize()

        view_name = f"ohlcv_{target_timeframe}"

        with self.engine.connect() as conn:
            try:
                # Create continuous aggregate
                query = text(f"""
                    CREATE MATERIALIZED VIEW {view_name}
                    WITH (timescaledb.continuous) AS
                    SELECT
                        time_bucket(:interval, time) AS time,
                        symbol,
                        :timeframe as timeframe,
                        FIRST(open, time) AS open,
                        MAX(high) AS high,
                        MIN(low) AS low,
                        LAST(close, time) AS close,
                        SUM(volume) AS volume,
                        SUM(trades) AS trades,
                        SUM(quote_volume) AS quote_volume
                    FROM ohlcv
                    WHERE timeframe = :source_timeframe
                    GROUP BY time_bucket(:interval, time), symbol
                    WITH NO DATA;
                """)

                # Map timeframe to interval
                interval_map = {
                    '1h': '1 hour',
                    '4h': '4 hours',
                    '1d': '1 day'
                }

                conn.execute(
                    query,
                    {
                        'interval': interval_map.get(target_timeframe, '1 hour'),
                        'timeframe': target_timeframe,
                        'source_timeframe': source_timeframe
                    }
                )
                conn.commit()
                logger.info(f"Created continuous aggregate: {view_name}")

            except Exception as e:
                logger.error(f"Error creating continuous aggregate: {e}")

    def add_retention_policy(self, retention_days: int = 365):
        """
        Add data retention policy to automatically drop old data.

        Args:
            retention_days: Number of days to retain data
        """
        if self.engine is None:
            self.initialize()

        with self.engine.connect() as conn:
            try:
                query = text(
                    "SELECT add_retention_policy('ohlcv', INTERVAL :days DAY, if_not_exists => TRUE)"
                )
                conn.execute(query, {'days': str(retention_days)})
                conn.commit()
                logger.info(f"Added retention policy: {retention_days} days")

            except Exception as e:
                logger.error(f"Error adding retention policy: {e}")


# Global TimescaleDB instance
timeseries_db = TimeSeriesDB()
