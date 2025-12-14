"""
Data fetching and management routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
import logging

from api.dependencies import get_data_provider
from core.models import DataFetchRequest
from data.providers.binance_provider import BinanceDataProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["Data"])


@router.post("/fetch")
async def fetch_historical_data(
    request: DataFetchRequest,
    data_provider: BinanceDataProvider = Depends(get_data_provider)
):
    """
    Fetch historical market data.

    Returns OHLCV data for the specified symbol and time range.
    """
    try:
        data = data_provider.fetch_historical(
            symbol=request.symbol,
            timeframe=request.timeframe.value,
            start_date=request.start_date,
            end_date=request.end_date
        )

        # Convert to JSON-serializable format
        data_dict = data.reset_index().to_dict(orient='records')

        return {
            'symbol': request.symbol,
            'timeframe': request.timeframe.value,
            'start_date': request.start_date,
            'end_date': request.end_date,
            'count': len(data_dict),
            'data': data_dict
        }

    except Exception as e:
        logger.error(f"Error fetching data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price/{symbol}")
async def get_current_price(
    symbol: str,
    data_provider: BinanceDataProvider = Depends(get_data_provider)
):
    """Get current market price for a symbol."""
    try:
        price = data_provider.get_current_price(symbol)
        return {
            'symbol': symbol,
            'price': price,
            'timestamp': datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error fetching price: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{symbol}")
async def get_orderbook(
    symbol: str,
    limit: int = 10,
    data_provider: BinanceDataProvider = Depends(get_data_provider)
):
    """Get order book for a symbol."""
    try:
        orderbook = data_provider.get_orderbook(symbol, limit)
        return {
            'symbol': symbol,
            'best_bid': orderbook['best_bid'],
            'best_ask': orderbook['best_ask'],
            'bids': orderbook['bids'][:limit],
            'asks': orderbook['asks'][:limit]
        }

    except Exception as e:
        logger.error(f"Error fetching orderbook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


from datetime import datetime
