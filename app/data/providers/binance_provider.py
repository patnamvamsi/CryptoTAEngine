"""
Binance data provider for fetching historical and live market data.
"""
from binance.client import Client
from binance import AsyncClient
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
import asyncio
import logging

from core.config import settings
from core.exceptions import DataFetchError

logger = logging.getLogger(__name__)


class BinanceDataProvider:
    """Fetch historical and live data from Binance."""

    # Timeframe mapping
    TIMEFRAME_MAP = {
        '1m': Client.KLINE_INTERVAL_1MINUTE,
        '5m': Client.KLINE_INTERVAL_5MINUTE,
        '15m': Client.KLINE_INTERVAL_15MINUTE,
        '30m': Client.KLINE_INTERVAL_30MINUTE,
        '1h': Client.KLINE_INTERVAL_1HOUR,
        '4h': Client.KLINE_INTERVAL_4HOUR,
        '1d': Client.KLINE_INTERVAL_1DAY,
    }

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Binance client.

        Args:
            api_key: Binance API key (uses settings if not provided)
            api_secret: Binance API secret (uses settings if not provided)
        """
        self.api_key = api_key or settings.BINANCE_API_KEY
        self.api_secret = api_secret or settings.BINANCE_API_SECRET

        if settings.BINANCE_TESTNET:
            self.client = Client(
                self.api_key,
                self.api_secret,
                testnet=True
            )
        else:
            self.client = Client(self.api_key, self.api_secret)

        logger.info(
            f"Initialized BinanceDataProvider "
            f"({'testnet' if settings.BINANCE_TESTNET else 'production'})"
        )

    def fetch_historical(
        self,
        symbol: str,
        timeframe: str = '15m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            start_date: Start datetime (default: 30 days ago)
            end_date: End datetime (default: now)
            limit: Maximum number of candles (max 1000 per request)

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume, ...]
        """
        try:
            # Default dates
            if end_date is None:
                end_date = datetime.utcnow()
            if start_date is None:
                start_date = end_date - timedelta(days=30)

            # Convert timeframe
            interval = self.TIMEFRAME_MAP.get(timeframe)
            if interval is None:
                raise ValueError(f"Invalid timeframe: {timeframe}")

            logger.info(
                f"Fetching {symbol} {timeframe} data from {start_date} to {end_date}"
            )

            # Fetch klines
            klines = self.client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=str(int(start_date.timestamp() * 1000)),
                end_str=str(int(end_date.timestamp() * 1000)),
                limit=limit
            )

            # Convert to DataFrame
            df = self._klines_to_dataframe(klines)

            logger.info(f"Fetched {len(df)} candles for {symbol}")

            return df

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise DataFetchError(f"Failed to fetch historical data: {e}")

    async def fetch_historical_async(
        self,
        symbol: str,
        timeframe: str = '15m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch historical data asynchronously.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            start_date: Start datetime
            end_date: End datetime

        Returns:
            DataFrame with OHLCV data
        """
        try:
            client = await AsyncClient.create(self.api_key, self.api_secret)

            # Default dates
            if end_date is None:
                end_date = datetime.utcnow()
            if start_date is None:
                start_date = end_date - timedelta(days=30)

            interval = self.TIMEFRAME_MAP.get(timeframe)
            if interval is None:
                raise ValueError(f"Invalid timeframe: {timeframe}")

            logger.info(
                f"Async fetching {symbol} {timeframe} from {start_date} to {end_date}"
            )

            klines = await client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=str(int(start_date.timestamp() * 1000)),
                end_str=str(int(end_date.timestamp() * 1000))
            )

            await client.close_connection()

            df = self._klines_to_dataframe(klines)
            logger.info(f"Async fetched {len(df)} candles for {symbol}")

            return df

        except Exception as e:
            logger.error(f"Error in async fetch: {e}")
            raise DataFetchError(f"Async fetch failed: {e}")

    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        timeframe: str = '15m',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols.

        Args:
            symbols: List of trading pairs
            timeframe: Candle timeframe
            start_date: Start datetime
            end_date: End datetime

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        async def fetch_all():
            tasks = [
                self.fetch_historical_async(symbol, timeframe, start_date, end_date)
                for symbol in symbols
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return dict(zip(symbols, results))

        return asyncio.run(fetch_all())

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            Current price
        """
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])

        except Exception as e:
            logger.error(f"Error fetching current price: {e}")
            raise DataFetchError(f"Failed to get current price: {e}")

    def get_orderbook(self, symbol: str, limit: int = 100) -> Dict:
        """
        Get order book for a symbol.

        Args:
            symbol: Trading pair
            limit: Depth of order book

        Returns:
            Dict with 'bids' and 'asks'
        """
        try:
            orderbook = self.client.get_order_book(symbol=symbol, limit=limit)
            return {
                'bids': orderbook['bids'],
                'asks': orderbook['asks'],
                'best_bid': float(orderbook['bids'][0][0]) if orderbook['bids'] else None,
                'best_ask': float(orderbook['asks'][0][0]) if orderbook['asks'] else None
            }

        except Exception as e:
            logger.error(f"Error fetching orderbook: {e}")
            raise DataFetchError(f"Failed to get orderbook: {e}")

    def get_account_balance(self) -> pd.DataFrame:
        """
        Get account balances.

        Returns:
            DataFrame with asset balances
        """
        try:
            account = self.client.get_account()
            balances = []

            for balance in account['balances']:
                free = float(balance['free'])
                locked = float(balance['locked'])

                if free > 0 or locked > 0:
                    balances.append({
                        'asset': balance['asset'],
                        'free': free,
                        'locked': locked,
                        'total': free + locked
                    })

            return pd.DataFrame(balances)

        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            raise DataFetchError(f"Failed to get account balance: {e}")

    def _klines_to_dataframe(self, klines: List) -> pd.DataFrame:
        """
        Convert Binance klines to DataFrame.

        Args:
            klines: Raw klines from Binance API

        Returns:
            Formatted DataFrame
        """
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Convert types
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume',
                    'taker_buy_base', 'taker_buy_quote']:
            df[col] = df[col].astype(float)

        df['trades'] = df['trades'].astype(int)

        # Set timestamp as index
        df.set_index('timestamp', inplace=True)

        # Keep only essential columns by default
        df = df[['open', 'high', 'low', 'close', 'volume', 'trades', 'quote_volume']]

        return df

    def validate_symbol(self, symbol: str) -> bool:
        """
        Check if a symbol is valid and tradeable.

        Args:
            symbol: Trading pair

        Returns:
            True if valid, False otherwise
        """
        try:
            info = self.client.get_symbol_info(symbol)
            return info is not None and info['status'] == 'TRADING'

        except Exception:
            return False
