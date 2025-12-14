"""
Pydantic models for API requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


class StrategyType(str, Enum):
    """Available trading strategies."""
    RSI = "rsi"
    GRID = "grid"
    MACD = "macd"
    BOLLINGER = "bollinger"


class BacktestStatus(str, Enum):
    """Backtest job status."""
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TimeFrame(str, Enum):
    """Available timeframes."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


# Request Models
class BacktestRequest(BaseModel):
    """Request model for backtesting a strategy."""
    strategy: StrategyType = Field(..., description="Trading strategy to backtest")
    symbol: str = Field(..., description="Trading pair symbol (e.g., BTCUSDT)")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    timeframe: TimeFrame = Field(TimeFrame.MINUTE_15, description="Data timeframe")
    initial_capital: float = Field(10000.0, gt=0, description="Initial capital for backtest")
    commission: float = Field(0.001, ge=0, le=0.1, description="Trading commission rate")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy-specific parameters")

    @validator('end_date')
    def validate_dates(cls, v, values):
        """Ensure end_date is after start_date."""
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "strategy": "rsi",
                "symbol": "BTCUSDT",
                "start_date": "2023-01-01T00:00:00",
                "end_date": "2023-12-31T23:59:59",
                "timeframe": "15m",
                "initial_capital": 10000.0,
                "commission": 0.001,
                "parameters": {
                    "rsi_period": 14,
                    "oversold": 30,
                    "overbought": 70
                }
            }
        }


class OptimizationRequest(BaseModel):
    """Request model for strategy parameter optimization."""
    strategy: StrategyType
    symbol: str
    start_date: datetime
    end_date: datetime
    timeframe: TimeFrame = TimeFrame.MINUTE_15
    initial_capital: float = 10000.0
    parameter_grid: Dict[str, List[Any]] = Field(..., description="Parameters to optimize")
    optimization_metric: str = Field("sharpe_ratio", description="Metric to optimize")

    class Config:
        json_schema_extra = {
            "example": {
                "strategy": "rsi",
                "symbol": "BTCUSDT",
                "start_date": "2023-01-01T00:00:00",
                "end_date": "2023-12-31T23:59:59",
                "timeframe": "15m",
                "initial_capital": 10000.0,
                "parameter_grid": {
                    "rsi_period": [10, 14, 20],
                    "oversold": [25, 30, 35],
                    "overbought": [65, 70, 75]
                },
                "optimization_metric": "sharpe_ratio"
            }
        }


class DataFetchRequest(BaseModel):
    """Request model for fetching historical data."""
    symbol: str
    start_date: datetime
    end_date: datetime
    timeframe: TimeFrame = TimeFrame.MINUTE_15
    source: str = Field("binance", description="Data source provider")


# Response Models
class PerformanceMetrics(BaseModel):
    """Performance metrics from a backtest."""
    # Returns
    total_return: float = Field(..., description="Total return percentage")
    annual_return: float = Field(..., description="Annualized return percentage")
    cagr: float = Field(..., description="Compound Annual Growth Rate")

    # Risk
    volatility: float = Field(..., description="Annualized volatility")
    max_drawdown: float = Field(..., description="Maximum drawdown percentage")
    var_95: float = Field(..., description="Value at Risk (95%)")
    cvar_95: float = Field(..., description="Conditional Value at Risk (95%)")

    # Risk-Adjusted
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    calmar_ratio: float = Field(..., description="Calmar ratio")

    # Trading
    total_trades: int = Field(..., description="Total number of trades")
    win_rate: float = Field(..., description="Percentage of winning trades")
    profit_factor: float = Field(..., description="Gross profit / Gross loss")
    avg_win: float = Field(..., description="Average winning trade")
    avg_loss: float = Field(..., description="Average losing trade")
    avg_trade: float = Field(..., description="Average trade P&L")

    # Optional benchmark comparison
    alpha: Optional[float] = Field(None, description="Alpha vs benchmark")
    beta: Optional[float] = Field(None, description="Beta vs benchmark")

    class Config:
        json_schema_extra = {
            "example": {
                "total_return": 25.5,
                "annual_return": 18.2,
                "cagr": 17.8,
                "volatility": 22.3,
                "max_drawdown": -15.2,
                "var_95": -2.1,
                "cvar_95": -3.5,
                "sharpe_ratio": 1.45,
                "sortino_ratio": 2.1,
                "calmar_ratio": 1.2,
                "total_trades": 120,
                "win_rate": 58.3,
                "profit_factor": 1.8,
                "avg_win": 150.0,
                "avg_loss": -80.0,
                "avg_trade": 45.5
            }
        }


class TradeRecord(BaseModel):
    """Individual trade record."""
    entry_date: datetime
    exit_date: Optional[datetime] = None
    symbol: str
    side: str  # BUY or SELL
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    commission: float = 0.0
    status: str = "open"  # open or closed


class BacktestResult(BaseModel):
    """Complete backtest result."""
    job_id: str
    strategy: StrategyType
    symbol: str
    start_date: datetime
    end_date: datetime
    timeframe: TimeFrame
    initial_capital: float
    final_capital: float
    parameters: Dict[str, Any]
    metrics: PerformanceMetrics
    trades: List[TradeRecord]
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    plot_html: Optional[str] = None
    execution_time: float = Field(..., description="Execution time in seconds")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BacktestJobResponse(BaseModel):
    """Response when submitting a backtest job."""
    job_id: str
    status: BacktestStatus
    message: str = "Backtest submitted successfully"
    estimated_time: Optional[int] = Field(None, description="Estimated completion time in seconds")


class BacktestStatusResponse(BaseModel):
    """Response for backtest job status check."""
    job_id: str
    status: BacktestStatus
    progress: Optional[float] = Field(None, ge=0, le=100, description="Progress percentage")
    message: Optional[str] = None
    result: Optional[BacktestResult] = None


class OptimizationResult(BaseModel):
    """Result from parameter optimization."""
    job_id: str
    strategy: StrategyType
    symbol: str
    best_parameters: Dict[str, Any]
    best_metric_value: float
    optimization_metric: str
    all_results: List[Dict[str, Any]]
    execution_time: float


class HealthResponse(BaseModel):
    """API health check response."""
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
