"""
Custom exceptions for the trading engine.
"""


class TradingEngineException(Exception):
    """Base exception for all trading engine errors."""
    pass


class ConfigurationError(TradingEngineException):
    """Raised when there's a configuration error."""
    pass


class DataFetchError(TradingEngineException):
    """Raised when data fetching fails."""
    pass


class BacktestError(TradingEngineException):
    """Raised when backtest execution fails."""
    pass


class StrategyError(TradingEngineException):
    """Raised when there's an error in strategy execution."""
    pass


class BrokerError(TradingEngineException):
    """Raised when there's an error communicating with the broker."""
    pass


class DatabaseError(TradingEngineException):
    """Raised when there's a database error."""
    pass


class CacheError(TradingEngineException):
    """Raised when there's a cache error."""
    pass


class ValidationError(TradingEngineException):
    """Raised when data validation fails."""
    pass
