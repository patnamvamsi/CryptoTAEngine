"""
Comprehensive performance metrics calculation for backtesting.
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from scipy import stats


class PerformanceMetrics:
    """Calculate comprehensive trading performance metrics."""

    TRADING_DAYS_PER_YEAR = 252
    RISK_FREE_RATE = 0.02  # 2% annual risk-free rate

    @staticmethod
    def calculate_all(
        portfolio_values: List[float],
        trades: List[Dict[str, Any]],
        initial_capital: float,
        benchmark_returns: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Calculate all performance metrics.

        Args:
            portfolio_values: Time series of portfolio values
            trades: List of trade dictionaries with 'pnl', 'commission', etc.
            initial_capital: Starting capital
            benchmark_returns: Optional benchmark returns for comparison

        Returns:
            Dictionary with all performance metrics
        """
        if len(portfolio_values) < 2:
            return PerformanceMetrics._empty_metrics()

        portfolio_values = np.array(portfolio_values)
        returns = np.diff(portfolio_values) / portfolio_values[:-1]

        metrics = {
            # Returns
            'total_return': PerformanceMetrics.total_return(portfolio_values),
            'annual_return': PerformanceMetrics.annualized_return(returns),
            'cagr': PerformanceMetrics.cagr(portfolio_values),

            # Risk
            'volatility': PerformanceMetrics.volatility(returns),
            'max_drawdown': PerformanceMetrics.max_drawdown(portfolio_values),
            'var_95': PerformanceMetrics.value_at_risk(returns, confidence=0.95),
            'cvar_95': PerformanceMetrics.conditional_var(returns, confidence=0.95),

            # Risk-Adjusted
            'sharpe_ratio': PerformanceMetrics.sharpe_ratio(returns),
            'sortino_ratio': PerformanceMetrics.sortino_ratio(returns),
            'calmar_ratio': PerformanceMetrics.calmar_ratio(portfolio_values),

            # Trading
            'total_trades': len(trades),
            'win_rate': PerformanceMetrics.win_rate(trades),
            'profit_factor': PerformanceMetrics.profit_factor(trades),
            'avg_win': PerformanceMetrics.avg_win(trades),
            'avg_loss': PerformanceMetrics.avg_loss(trades),
            'avg_trade': PerformanceMetrics.avg_trade(trades),
        }

        # Benchmark comparison if provided
        if benchmark_returns is not None and len(benchmark_returns) == len(returns):
            metrics['alpha'] = PerformanceMetrics.alpha(returns, benchmark_returns)
            metrics['beta'] = PerformanceMetrics.beta(returns, benchmark_returns)
        else:
            metrics['alpha'] = None
            metrics['beta'] = None

        return metrics

    @staticmethod
    def _empty_metrics() -> Dict[str, Any]:
        """Return empty metrics dict when insufficient data."""
        return {
            'total_return': 0.0,
            'annual_return': 0.0,
            'cagr': 0.0,
            'volatility': 0.0,
            'max_drawdown': 0.0,
            'var_95': 0.0,
            'cvar_95': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'calmar_ratio': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'avg_trade': 0.0,
            'alpha': None,
            'beta': None
        }

    # Return Metrics
    @staticmethod
    def total_return(portfolio_values: np.ndarray) -> float:
        """Calculate total return percentage."""
        if len(portfolio_values) < 2:
            return 0.0
        return float((portfolio_values[-1] / portfolio_values[0] - 1) * 100)

    @staticmethod
    def annualized_return(returns: np.ndarray) -> float:
        """Calculate annualized return percentage."""
        if len(returns) == 0:
            return 0.0
        mean_return = np.mean(returns)
        return float(mean_return * PerformanceMetrics.TRADING_DAYS_PER_YEAR * 100)

    @staticmethod
    def cagr(portfolio_values: np.ndarray) -> float:
        """Calculate Compound Annual Growth Rate."""
        if len(portfolio_values) < 2:
            return 0.0
        total_return = portfolio_values[-1] / portfolio_values[0]
        years = len(portfolio_values) / PerformanceMetrics.TRADING_DAYS_PER_YEAR
        if years <= 0:
            return 0.0
        return float((total_return ** (1 / years) - 1) * 100)

    # Risk Metrics
    @staticmethod
    def volatility(returns: np.ndarray) -> float:
        """Calculate annualized volatility (standard deviation)."""
        if len(returns) < 2:
            return 0.0
        return float(np.std(returns) * np.sqrt(PerformanceMetrics.TRADING_DAYS_PER_YEAR) * 100)

    @staticmethod
    def max_drawdown(portfolio_values: np.ndarray) -> float:
        """Calculate maximum drawdown percentage."""
        if len(portfolio_values) < 2:
            return 0.0

        running_max = np.maximum.accumulate(portfolio_values)
        drawdown = (portfolio_values - running_max) / running_max
        return float(np.min(drawdown) * 100)

    @staticmethod
    def value_at_risk(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Calculate Value at Risk at given confidence level."""
        if len(returns) == 0:
            return 0.0
        return float(np.percentile(returns, (1 - confidence) * 100) * 100)

    @staticmethod
    def conditional_var(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)."""
        if len(returns) == 0:
            return 0.0
        var = np.percentile(returns, (1 - confidence) * 100)
        return float(returns[returns <= var].mean() * 100)

    # Risk-Adjusted Metrics
    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: Optional[float] = None) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0

        if risk_free_rate is None:
            risk_free_rate = PerformanceMetrics.RISK_FREE_RATE

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        daily_rf = risk_free_rate / PerformanceMetrics.TRADING_DAYS_PER_YEAR
        excess_return = mean_return - daily_rf

        return float(excess_return / std_return * np.sqrt(PerformanceMetrics.TRADING_DAYS_PER_YEAR))

    @staticmethod
    def sortino_ratio(returns: np.ndarray, risk_free_rate: Optional[float] = None) -> float:
        """Calculate Sortino ratio (uses downside deviation)."""
        if len(returns) < 2:
            return 0.0

        if risk_free_rate is None:
            risk_free_rate = PerformanceMetrics.RISK_FREE_RATE

        mean_return = np.mean(returns)
        daily_rf = risk_free_rate / PerformanceMetrics.TRADING_DAYS_PER_YEAR

        # Downside deviation (only negative returns)
        downside_returns = returns[returns < daily_rf]
        if len(downside_returns) == 0:
            return 0.0

        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0.0

        excess_return = mean_return - daily_rf
        return float(excess_return / downside_std * np.sqrt(PerformanceMetrics.TRADING_DAYS_PER_YEAR))

    @staticmethod
    def calmar_ratio(portfolio_values: np.ndarray) -> float:
        """Calculate Calmar ratio (CAGR / Max Drawdown)."""
        max_dd = abs(PerformanceMetrics.max_drawdown(portfolio_values))
        if max_dd == 0:
            return 0.0

        cagr_val = PerformanceMetrics.cagr(portfolio_values)
        return float(cagr_val / max_dd)

    # Trading Metrics
    @staticmethod
    def win_rate(trades: List[Dict[str, Any]]) -> float:
        """Calculate win rate percentage."""
        if len(trades) == 0:
            return 0.0

        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        return float(wins / len(trades) * 100)

    @staticmethod
    def profit_factor(trades: List[Dict[str, Any]]) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        if len(trades) == 0:
            return 0.0

        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0

        return float(gross_profit / gross_loss)

    @staticmethod
    def avg_win(trades: List[Dict[str, Any]]) -> float:
        """Calculate average winning trade."""
        winning_trades = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0]
        if len(winning_trades) == 0:
            return 0.0
        return float(np.mean(winning_trades))

    @staticmethod
    def avg_loss(trades: List[Dict[str, Any]]) -> float:
        """Calculate average losing trade."""
        losing_trades = [t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0]
        if len(losing_trades) == 0:
            return 0.0
        return float(np.mean(losing_trades))

    @staticmethod
    def avg_trade(trades: List[Dict[str, Any]]) -> float:
        """Calculate average trade P&L."""
        if len(trades) == 0:
            return 0.0
        return float(np.mean([t.get('pnl', 0) for t in trades]))

    # Benchmark Comparison
    @staticmethod
    def alpha(returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
        """Calculate alpha (excess return vs benchmark)."""
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 0.0

        # CAPM: alpha = mean(returns) - beta * mean(benchmark_returns)
        beta_val = PerformanceMetrics.beta(returns, benchmark_returns)
        mean_return = np.mean(returns)
        mean_benchmark = np.mean(benchmark_returns)

        alpha_val = mean_return - (beta_val * mean_benchmark)
        return float(alpha_val * PerformanceMetrics.TRADING_DAYS_PER_YEAR * 100)

    @staticmethod
    def beta(returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
        """Calculate beta (systematic risk vs benchmark)."""
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 0.0

        # Beta = Cov(returns, benchmark) / Var(benchmark)
        covariance = np.cov(returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)

        if benchmark_variance == 0:
            return 0.0

        return float(covariance / benchmark_variance)

    @staticmethod
    def information_ratio(returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
        """Calculate information ratio."""
        if len(returns) != len(benchmark_returns) or len(returns) < 2:
            return 0.0

        excess_returns = returns - benchmark_returns
        tracking_error = np.std(excess_returns)

        if tracking_error == 0:
            return 0.0

        return float(np.mean(excess_returns) / tracking_error * np.sqrt(PerformanceMetrics.TRADING_DAYS_PER_YEAR))

    @staticmethod
    def calculate_equity_curve(portfolio_values: List[float], dates: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """
        Generate equity curve data for plotting.

        Args:
            portfolio_values: Time series of portfolio values
            dates: Optional dates corresponding to values

        Returns:
            List of dicts with date and value
        """
        if dates is None:
            dates = list(range(len(portfolio_values)))

        return [
            {'date': str(date), 'value': float(value)}
            for date, value in zip(dates, portfolio_values)
        ]
