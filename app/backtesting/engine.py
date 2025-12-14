"""
Backtesting engine with parallel processing and optimization support.
"""
import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Type
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
from uuid import uuid4
import time
import logging

from backtesting.metrics import PerformanceMetrics
from strategies.base import BaseStrategy
from core.config import settings
from core.exceptions import BacktestError

logger = logging.getLogger(__name__)


class CustomCerebro(bt.Cerebro):
    """
    Custom Cerebro class that returns plot figures without displaying.
    Allows non-blocking plot generation for API responses.
    """

    def plot(self, plotter=None, numfigs=1, iplot=True, start=None, end=None,
             width=16, height=9, dpi=300, tight=True, use=None, **kwargs):
        """Override plot to return figures instead of showing."""
        if self._exactbars > 0:
            return

        if not plotter:
            from backtrader import plot
            if self.p.oldsync:
                plotter = plot.Plot_OldSync(**kwargs)
            else:
                plotter = plot.Plot(**kwargs)

        figs = []
        for stratlist in self.runstrats:
            for si, strat in enumerate(stratlist):
                rfig = plotter.plot(strat, figid=si * 100,
                                    numfigs=numfigs, iplot=iplot,
                                    start=start, end=end, use=use)
                figs.append(rfig)

        return figs


class BacktestEngine:
    """
    Main backtesting engine with support for:
    - Single strategy backtests
    - Parameter optimization
    - Walk-forward analysis
    - Monte Carlo simulations
    - Parallel execution
    """

    def __init__(self, n_workers: Optional[int] = None):
        """
        Initialize backtesting engine.

        Args:
            n_workers: Number of parallel workers (defaults to CPU count)
        """
        self.n_workers = n_workers or min(mp.cpu_count(), settings.MAX_PARALLEL_BACKTESTS)
        logger.info(f"Initialized BacktestEngine with {self.n_workers} workers")

    def run_backtest(
        self,
        strategy_class: Type[BaseStrategy],
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        parameters: Optional[Dict[str, Any]] = None,
        benchmark_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Run a single backtest.

        Args:
            strategy_class: Strategy class to test
            data: DataFrame with OHLCV data
            initial_capital: Starting capital
            commission: Commission rate
            parameters: Strategy parameters
            benchmark_data: Optional benchmark for comparison

        Returns:
            Dictionary with backtest results
        """
        start_time = time.time()
        job_id = str(uuid4())

        try:
            logger.info(f"Starting backtest {job_id} for {strategy_class.__name__}")

            # Create Cerebro instance
            cerebro = CustomCerebro()

            # Set initial cash and commission
            cerebro.broker.setcash(initial_capital)
            cerebro.broker.setcommission(commission=commission)

            # Add data feed
            data_feed = self._prepare_data_feed(data)
            cerebro.adddata(data_feed)

            # Add strategy with parameters
            if parameters:
                cerebro.addstrategy(strategy_class, **parameters)
            else:
                cerebro.addstrategy(strategy_class)

            # Run backtest
            logger.info("Running backtest...")
            results = cerebro.run()
            strategy_instance = results[0]

            # Get final value
            final_value = cerebro.broker.getvalue()

            # Extract data from strategy
            trades = strategy_instance.get_trades()
            portfolio_values = strategy_instance.get_portfolio_values()
            dates = strategy_instance.get_dates()

            # Calculate metrics
            benchmark_returns = None
            if benchmark_data is not None:
                benchmark_returns = self._calculate_benchmark_returns(benchmark_data)

            metrics = PerformanceMetrics.calculate_all(
                portfolio_values=portfolio_values,
                trades=trades,
                initial_capital=initial_capital,
                benchmark_returns=benchmark_returns
            )

            # Generate equity curve
            equity_curve = PerformanceMetrics.calculate_equity_curve(
                portfolio_values, dates
            )

            # Generate plot
            plot_html = None
            try:
                import plotly
                div = cerebro.plot()[0][0]
                plot_html = plotly.offline.plot_mpl(div, output_type='div')
            except Exception as e:
                logger.warning(f"Could not generate plot: {e}")

            execution_time = time.time() - start_time

            result = {
                'job_id': job_id,
                'strategy': strategy_class.__name__,
                'initial_capital': initial_capital,
                'final_capital': final_value,
                'parameters': parameters or {},
                'metrics': metrics,
                'trades': trades,
                'equity_curve': equity_curve,
                'plot_html': plot_html,
                'execution_time': execution_time,
                'status': 'completed'
            }

            logger.info(
                f"Backtest {job_id} completed in {execution_time:.2f}s. "
                f"Return: {metrics['total_return']:.2f}%, Sharpe: {metrics['sharpe_ratio']:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Backtest {job_id} failed: {e}", exc_info=True)
            return {
                'job_id': job_id,
                'status': 'failed',
                'error': str(e),
                'execution_time': time.time() - start_time
            }

    def optimize_parameters(
        self,
        strategy_class: Type[BaseStrategy],
        data: pd.DataFrame,
        parameter_grid: Dict[str, List[Any]],
        optimization_metric: str = 'sharpe_ratio',
        initial_capital: float = 10000.0,
        commission: float = 0.001
    ) -> Dict[str, Any]:
        """
        Optimize strategy parameters using grid search.

        Args:
            strategy_class: Strategy class to optimize
            data: OHLCV data
            parameter_grid: Dict of parameter names to lists of values
            optimization_metric: Metric to optimize (sharpe_ratio, total_return, etc.)
            initial_capital: Starting capital
            commission: Commission rate

        Returns:
            Optimization results with best parameters
        """
        start_time = time.time()
        job_id = str(uuid4())

        logger.info(f"Starting optimization {job_id} for {strategy_class.__name__}")

        # Generate all parameter combinations
        param_combinations = self._generate_param_combinations(parameter_grid)
        total_combinations = len(param_combinations)

        logger.info(f"Testing {total_combinations} parameter combinations")

        # Run backtests in parallel
        results = []

        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            # Submit all jobs
            futures = {
                executor.submit(
                    self._run_single_optimization,
                    strategy_class,
                    data,
                    params,
                    initial_capital,
                    commission
                ): params
                for params in param_combinations
            }

            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Optimization run failed: {e}")

        # Find best parameters
        if not results:
            raise BacktestError("No successful optimization runs")

        # Sort by optimization metric
        results.sort(key=lambda x: x['metrics'].get(optimization_metric, 0), reverse=True)
        best_result = results[0]

        execution_time = time.time() - start_time

        optimization_result = {
            'job_id': job_id,
            'strategy': strategy_class.__name__,
            'best_parameters': best_result['parameters'],
            'best_metric_value': best_result['metrics'][optimization_metric],
            'optimization_metric': optimization_metric,
            'all_results': [
                {
                    'parameters': r['parameters'],
                    'metrics': r['metrics']
                }
                for r in results
            ],
            'total_combinations': total_combinations,
            'execution_time': execution_time,
            'status': 'completed'
        }

        logger.info(
            f"Optimization {job_id} completed in {execution_time:.2f}s. "
            f"Best {optimization_metric}: {best_result['metrics'][optimization_metric]:.2f}"
        )

        return optimization_result

    def walk_forward_analysis(
        self,
        strategy_class: Type[BaseStrategy],
        data: pd.DataFrame,
        train_period: int = 252,  # trading days
        test_period: int = 63,
        initial_capital: float = 10000.0,
        commission: float = 0.001
    ) -> Dict[str, Any]:
        """
        Perform walk-forward analysis.

        Splits data into train/test windows, optimizes on train, tests on test.

        Args:
            strategy_class: Strategy to test
            data: Full dataset
            train_period: Training window size (days)
            test_period: Testing window size (days)
            initial_capital: Starting capital
            commission: Commission rate

        Returns:
            Walk-forward analysis results
        """
        logger.info(f"Starting walk-forward analysis for {strategy_class.__name__}")

        # Split data into windows
        windows = self._create_windows(data, train_period, test_period)

        results = []
        for i, (train_data, test_data) in enumerate(windows):
            logger.info(f"Processing window {i + 1}/{len(windows)}")

            # TODO: Optimize parameters on train_data
            # For now, just test on test_data with default params

            window_result = self.run_backtest(
                strategy_class=strategy_class,
                data=test_data,
                initial_capital=initial_capital,
                commission=commission
            )

            results.append(window_result)

        return {
            'strategy': strategy_class.__name__,
            'windows': len(windows),
            'results': results,
            'status': 'completed'
        }

    def _prepare_data_feed(self, data: pd.DataFrame) -> bt.feeds.PandasData:
        """Convert DataFrame to Backtrader data feed."""
        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in data.columns]

        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Ensure datetime index
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'timestamp' in data.columns:
                data = data.set_index('timestamp')
            elif 'date' in data.columns:
                data = data.set_index('date')
            else:
                raise ValueError("Data must have datetime index or timestamp/date column")

        # Create Backtrader data feed
        data_feed = bt.feeds.PandasData(dataname=data)
        return data_feed

    def _calculate_benchmark_returns(self, benchmark_data: pd.DataFrame) -> np.ndarray:
        """Calculate returns from benchmark data."""
        if 'close' in benchmark_data.columns:
            prices = benchmark_data['close'].values
        else:
            prices = benchmark_data.values.flatten()

        returns = np.diff(prices) / prices[:-1]
        return returns

    def _generate_param_combinations(
        self,
        parameter_grid: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """Generate all combinations from parameter grid."""
        import itertools

        keys = parameter_grid.keys()
        values = parameter_grid.values()

        combinations = []
        for combination in itertools.product(*values):
            param_dict = dict(zip(keys, combination))
            combinations.append(param_dict)

        return combinations

    def _run_single_optimization(
        self,
        strategy_class: Type[BaseStrategy],
        data: pd.DataFrame,
        parameters: Dict[str, Any],
        initial_capital: float,
        commission: float
    ) -> Dict[str, Any]:
        """Run a single optimization iteration (for parallel execution)."""
        result = self.run_backtest(
            strategy_class=strategy_class,
            data=data,
            initial_capital=initial_capital,
            commission=commission,
            parameters=parameters
        )
        return result

    def _create_windows(
        self,
        data: pd.DataFrame,
        train_period: int,
        test_period: int
    ) -> List[tuple]:
        """Create train/test windows for walk-forward analysis."""
        windows = []
        total_period = train_period + test_period

        start_idx = 0
        while start_idx + total_period <= len(data):
            train_end = start_idx + train_period
            test_end = train_end + test_period

            train_data = data.iloc[start_idx:train_end]
            test_data = data.iloc[train_end:test_end]

            windows.append((train_data, test_data))

            # Move window forward
            start_idx += test_period

        return windows
