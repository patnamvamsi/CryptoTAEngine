"""
Celery tasks for distributed backtesting.
"""
from celery import Task
import pandas as pd
from typing import Dict, Any
import logging

from celery_app import celery_app
from backtesting.engine import BacktestEngine
from strategies.rsi_strategy import RSIStrategy
from data.storage.database import db_manager, BacktestRun
from utils.cache import backtest_cache

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management."""

    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = next(db_manager.get_db())
        return self._db


@celery_app.task(bind=True, base=DatabaseTask)
def run_backtest_task(
    self,
    job_id: str,
    strategy_name: str,
    symbol: str,
    data_dict: dict,
    initial_capital: float,
    commission: float,
    parameters: Dict[str, Any]
):
    """
    Celery task for running backtests.

    Args:
        job_id: Backtest job ID
        strategy_name: Name of strategy
        symbol: Trading symbol
        data_dict: OHLCV data as dictionary
        initial_capital: Starting capital
        commission: Commission rate
        parameters: Strategy parameters

    Returns:
        Backtest results
    """
    logger.info(f"Starting backtest task {job_id} for {strategy_name} on {symbol}")

    try:
        # Update status
        backtest_run = self.db.query(BacktestRun).filter(
            BacktestRun.id == job_id
        ).first()

        if backtest_run:
            backtest_run.status = 'running'
            self.db.commit()

        # Convert data dict back to DataFrame
        data = pd.DataFrame(data_dict)
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)

        # Get strategy class (simplified - should use strategy registry)
        strategy_class = RSIStrategy  # TODO: Use strategy registry

        # Run backtest
        engine = BacktestEngine()
        result = engine.run_backtest(
            strategy_class=strategy_class,
            data=data,
            initial_capital=initial_capital,
            commission=commission,
            parameters=parameters
        )

        # Update database
        if backtest_run:
            backtest_run.status = 'completed'
            backtest_run.final_capital = result['final_capital']
            backtest_run.total_return = result['metrics']['total_return']
            backtest_run.sharpe_ratio = result['metrics']['sharpe_ratio']
            backtest_run.max_drawdown = result['metrics']['max_drawdown']
            backtest_run.total_trades = result['metrics']['total_trades']
            backtest_run.win_rate = result['metrics']['win_rate']
            backtest_run.execution_time = result['execution_time']
            backtest_run.full_results = result
            self.db.commit()

        # Cache result
        backtest_cache.cache_backtest_result(
            strategy=strategy_name,
            symbol=symbol,
            start_date=str(data.index[0]),
            end_date=str(data.index[-1]),
            parameters=parameters,
            result=result
        )

        logger.info(f"Backtest task {job_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Backtest task {job_id} failed: {e}", exc_info=True)

        # Update database
        if backtest_run:
            backtest_run.status = 'failed'
            backtest_run.error_message = str(e)
            self.db.commit()

        raise


@celery_app.task
def run_optimization_task(
    job_id: str,
    strategy_name: str,
    symbol: str,
    data_dict: dict,
    parameter_grid: Dict[str, list],
    optimization_metric: str,
    initial_capital: float,
    commission: float
):
    """
    Celery task for parameter optimization.

    Args:
        job_id: Optimization job ID
        strategy_name: Strategy name
        symbol: Trading symbol
        data_dict: OHLCV data
        parameter_grid: Parameters to optimize
        optimization_metric: Metric to optimize
        initial_capital: Starting capital
        commission: Commission rate

    Returns:
        Optimization results
    """
    logger.info(f"Starting optimization task {job_id}")

    try:
        # Convert data
        data = pd.DataFrame(data_dict)
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data.set_index('timestamp', inplace=True)

        # Get strategy class
        strategy_class = RSIStrategy  # TODO: Use registry

        # Run optimization
        engine = BacktestEngine()
        result = engine.optimize_parameters(
            strategy_class=strategy_class,
            data=data,
            parameter_grid=parameter_grid,
            optimization_metric=optimization_metric,
            initial_capital=initial_capital,
            commission=commission
        )

        logger.info(f"Optimization task {job_id} completed")
        return result

    except Exception as e:
        logger.error(f"Optimization task {job_id} failed: {e}", exc_info=True)
        raise


@celery_app.task
def cleanup_old_backtests(days: int = 30):
    """
    Periodic task to clean up old backtest results.

    Args:
        days: Delete backtests older than this many days
    """
    from datetime import datetime, timedelta

    logger.info(f"Cleaning up backtests older than {days} days")

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        db = next(db_manager.get_db())
        deleted = db.query(BacktestRun).filter(
            BacktestRun.created_at < cutoff_date,
            BacktestRun.status == 'completed'
        ).delete()

        db.commit()
        logger.info(f"Deleted {deleted} old backtest records")

    except Exception as e:
        logger.error(f"Cleanup task failed: {e}", exc_info=True)
