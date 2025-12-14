"""
Data provider that reads from CryptoMarketData's existing TimescaleDB tables.

This provider integrates with the CryptoMarketData microservice which
continuously populates TimescaleDB with OHLCV data from Binance and Zerodha.

Table naming convention (from CryptoMarketData):
- Binance: binance_{symbol}_kline_{interval}
  Example: binance_btcusdt_kline_1m, binance_ethusdt_kline_5m
- Zerodha: zerodha_{symbol}_kline_{interval}
  Example: zerodha_reliance_kline_1m, zerodha_tcs_kline_1h
"""
from sqlalchemy import text
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict
import logging

from data.storage.timeseries import timeseries_db
from core.exceptions import DataFetchError
from core.config import settings

logger = logging.getLogger(__name__)


class SharedTimescaleProvider:
    """
    Data provider that reads from CryptoMarketData's existing TimescaleDB.

    Benefits:
    - No data duplication
    - Real-time data from CryptoMarketData's streaming
    - Access to multiple exchanges (Binance, Zerodha)
    - Historical data already populated
    """

    # Timeframe mapping (consistent with CryptoMarketData)
    TIMEFRAME_MAP = {
        '1m': '1m',
        '3m': '3m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '2h': '2h',
        '4h': '4h',
        '6h': '6h',
        '8h': '8h',
        '12h': '12h',
        '1d': '1d',
        '3d': '3d',
        '1w': '1w',
        '1M': '1M'
    }

    def __init__(self):
        """Initialize the shared TimescaleDB provider."""
        self.db = timeseries_db
        if self.db.engine is None:
            self.db.initialize()

        logger.info("Initialized SharedTimescaleProvider (using CryptoMarketData tables)")

    def _get_table_name(self, exchange: str, symbol: str, timeframe: str) -> str:
        """
        Construct table name following CryptoMarketData convention.

        Args:
            exchange: 'binance' or 'zerodha'
            symbol: Trading symbol (lowercase)
            timeframe: Interval (1m, 5m, 1h, etc.)

        Returns:
            Table name like: binance_btcusdt_kline_1m
        """
        # Normalize inputs
        exchange = exchange.lower()
        symbol = symbol.lower()
        timeframe = self.TIMEFRAME_MAP.get(timeframe, timeframe)

        return f"{exchange}_{symbol}_kline_{timeframe}"

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        exchange: str = 'binance',
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from existing CryptoMarketData tables.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT', 'RELIANCE')
            timeframe: Candle interval (1m, 5m, 15m, 1h, etc.)
            start_date: Start datetime (optional)
            end_date: End datetime (optional)
            exchange: 'binance' or 'zerodha'
            limit: Maximum number of candles to fetch

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume, ...]
        """
        try:
            table_name = self._get_table_name(exchange, symbol, timeframe)

            logger.info(
                f"Fetching OHLCV from {table_name}: "
                f"{start_date} to {end_date}, limit={limit}"
            )

            # Build query
            query_parts = [f"SELECT * FROM {table_name}"]
            params = {}

            # Add WHERE clauses
            where_clauses = []
            if start_date:
                where_clauses.append("open_time >= :start_date")
                params['start_date'] = start_date
            if end_date:
                where_clauses.append("open_time <= :end_date")
                params['end_date'] = end_date

            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))

            # Add ordering
            query_parts.append("ORDER BY open_time ASC")

            # Add limit
            if limit:
                query_parts.append(f"LIMIT :limit")
                params['limit'] = limit

            query_str = " ".join(query_parts)
            query = text(query_str)

            # Execute query
            df = pd.read_sql(query, self.db.engine, params=params)

            if df.empty:
                logger.warning(f"No data found in {table_name}")
                return df

            # Rename columns to standard format
            column_mapping = {
                'open_time': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'trades': 'trades',
                'quote_asset_volume': 'quote_volume'
            }

            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

            # Set timestamp as index
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)

            logger.info(f"Fetched {len(df)} candles from {table_name}")
            return df

        except Exception as e:
            logger.error(f"Error fetching OHLCV from {table_name}: {e}", exc_info=True)
            raise DataFetchError(f"Failed to fetch OHLCV: {e}")

    def get_available_symbols(self, exchange: str = 'binance', active_only: bool = True) -> List[Dict]:
        """
        Get list of available symbols from CryptoMarketData.

        Args:
            exchange: 'binance' or 'zerodha'
            active_only: Only return active symbols

        Returns:
            List of symbol dictionaries
        """
        try:
            if exchange.lower() == 'binance':
                # Query binance_symbols table
                query = """
                    SELECT symbol, status, baseAsset as base_asset,
                           quoteAsset as quote_asset, priority, active
                    FROM binance_symbols
                """
                if active_only:
                    query += " WHERE active = true"
                query += " ORDER BY priority DESC, symbol ASC"

            else:  # zerodha or unified symbols table
                query = """
                    SELECT symbol, status, base_asset, quote_asset,
                           priority, active, exchange
                    FROM symbols
                    WHERE exchange = :exchange
                """
                if active_only:
                    query += " AND active = true"
                query += " ORDER BY priority DESC, symbol ASC"

            df = pd.read_sql(
                text(query),
                self.db.engine,
                params={'exchange': exchange} if exchange != 'binance' else {}
            )

            return df.to_dict('records')

        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            return []

    def check_table_exists(self, exchange: str, symbol: str, timeframe: str) -> bool:
        """
        Check if table exists for given symbol/timeframe.

        Args:
            exchange: 'binance' or 'zerodha'
            symbol: Trading symbol
            timeframe: Interval

        Returns:
            True if table exists
        """
        try:
            table_name = self._get_table_name(exchange, symbol, timeframe)

            query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                )
            """)

            result = self.db.engine.execute(query, {'table_name': table_name})
            exists = result.scalar()

            logger.debug(f"Table {table_name} exists: {exists}")
            return exists

        except Exception as e:
            logger.error(f"Error checking table existence: {e}")
            return False

    def get_latest_timestamp(self, exchange: str, symbol: str, timeframe: str) -> Optional[datetime]:
        """
        Get the most recent timestamp for a symbol/timeframe.

        Args:
            exchange: 'binance' or 'zerodha'
            symbol: Trading symbol
            timeframe: Interval

        Returns:
            Latest timestamp or None
        """
        try:
            table_name = self._get_table_name(exchange, symbol, timeframe)

            query = text(f"""
                SELECT MAX(open_time) as latest
                FROM {table_name}
            """)

            result = self.db.engine.execute(query)
            row = result.fetchone()

            return row[0] if row and row[0] else None

        except Exception as e:
            logger.error(f"Error getting latest timestamp: {e}")
            return None

    def get_data_summary(self, exchange: str, symbol: str, timeframe: str) -> Dict:
        """
        Get summary statistics for a symbol/timeframe.

        Args:
            exchange: 'binance' or 'zerodha'
            symbol: Trading symbol
            timeframe: Interval

        Returns:
            Dictionary with count, min_time, max_time, etc.
        """
        try:
            table_name = self._get_table_name(exchange, symbol, timeframe)

            query = text(f"""
                SELECT
                    COUNT(*) as count,
                    MIN(open_time) as min_time,
                    MAX(open_time) as max_time,
                    MIN(low) as min_price,
                    MAX(high) as max_price,
                    SUM(volume) as total_volume
                FROM {table_name}
            """)

            result = self.db.engine.execute(query)
            row = result.fetchone()

            if row:
                return {
                    'table_name': table_name,
                    'count': row[0],
                    'min_time': row[1],
                    'max_time': row[2],
                    'min_price': float(row[3]) if row[3] else None,
                    'max_price': float(row[4]) if row[4] else None,
                    'total_volume': float(row[5]) if row[5] else None
                }

            return {}

        except Exception as e:
            logger.error(f"Error getting data summary: {e}")
            return {}


# Global instance
shared_timescale_provider = SharedTimescaleProvider()
