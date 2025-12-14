"""
Backtest API routes.
"""
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime
import logging

from api.dependencies import (
    get_db,
    get_backtest_engine,
    get_backtest_cache,
    get_data_provider
)
from core.models import (
    BacktestRequest,
    BacktestJobResponse,
    BacktestStatusResponse,
    BacktestResult,
    OptimizationRequest,
    BacktestStatus
)
from data.storage.database import BacktestRun
from backtesting.engine import BacktestEngine
from utils.cache import BacktestCache
from data.providers.binance_provider import BinanceDataProvider
from strategies.rsi_strategy import RSIStrategy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtesting"])


# Strategy mapping
STRATEGY_MAP = {
    "rsi": RSIStrategy,
    # Add more strategies here
}


@router.post("/run", response_model=BacktestJobResponse)
async def submit_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    engine: BacktestEngine = Depends(get_backtest_engine),
    cache: BacktestCache = Depends(get_backtest_cache),
    data_provider: BinanceDataProvider = Depends(get_data_provider)
):
    """
    Submit a backtest job.

    The backtest will run in the background and results can be retrieved
    using the returned job_id.
    """
    try:
        # Check cache first
        cached_result = cache.get_cached_backtest(
            strategy=request.strategy.value,
            symbol=request.symbol,
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            parameters=request.parameters
        )

        if cached_result:
            logger.info(f"Returning cached backtest result")
            return BacktestJobResponse(
                job_id=cached_result['job_id'],
                status=BacktestStatus.COMPLETED,
                message="Backtest retrieved from cache"
            )

        # Get strategy class
        strategy_class = STRATEGY_MAP.get(request.strategy.value)
        if not strategy_class:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy: {request.strategy}"
            )

        # Fetch data
        logger.info(f"Fetching data for {request.symbol}")
        data = data_provider.fetch_historical(
            symbol=request.symbol,
            timeframe=request.timeframe.value,
            start_date=request.start_date,
            end_date=request.end_date
        )

        if data.empty:
            raise HTTPException(
                status_code=404,
                detail="No data found for the specified parameters"
            )

        # Create database record
        backtest_run = BacktestRun(
            id=str(uuid4()),
            strategy=request.strategy.value,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            timeframe=request.timeframe.value,
            initial_capital=request.initial_capital,
            commission=request.commission,
            parameters=request.parameters,
            status='submitted'
        )
        db.add(backtest_run)
        db.commit()

        # Run backtest in background
        background_tasks.add_task(
            run_backtest_async,
            backtest_run.id,
            strategy_class,
            data,
            request,
            engine,
            cache,
            db
        )

        return BacktestJobResponse(
            job_id=backtest_run.id,
            status=BacktestStatus.SUBMITTED,
            message="Backtest submitted successfully"
        )

    except Exception as e:
        logger.error(f"Error submitting backtest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/status", response_model=BacktestStatusResponse)
async def get_backtest_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get the status of a backtest job."""
    backtest_run = db.query(BacktestRun).filter(BacktestRun.id == job_id).first()

    if not backtest_run:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    response = BacktestStatusResponse(
        job_id=job_id,
        status=BacktestStatus(backtest_run.status),
        message=backtest_run.error_message if backtest_run.status == 'failed' else None
    )

    # If completed, include results
    if backtest_run.status == 'completed' and backtest_run.full_results:
        response.result = backtest_run.full_results

    return response


@router.get("/{job_id}/results", response_model=BacktestResult)
async def get_backtest_results(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get the full results of a completed backtest."""
    backtest_run = db.query(BacktestRun).filter(BacktestRun.id == job_id).first()

    if not backtest_run:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    if backtest_run.status != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Backtest is not completed. Current status: {backtest_run.status}"
        )

    return backtest_run.full_results


@router.post("/optimize", response_model=BacktestJobResponse)
async def optimize_strategy(
    request: OptimizationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    engine: BacktestEngine = Depends(get_backtest_engine),
    data_provider: BinanceDataProvider = Depends(get_data_provider)
):
    """
    Optimize strategy parameters.

    Runs grid search over parameter combinations to find optimal values.
    """
    try:
        # Get strategy class
        strategy_class = STRATEGY_MAP.get(request.strategy.value)
        if not strategy_class:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy: {request.strategy}"
            )

        # Fetch data
        data = data_provider.fetch_historical(
            symbol=request.symbol,
            timeframe=request.timeframe.value,
            start_date=request.start_date,
            end_date=request.end_date
        )

        if data.empty:
            raise HTTPException(
                status_code=404,
                detail="No data found"
            )

        from uuid import uuid4
        job_id = str(uuid4())

        # Run optimization in background
        background_tasks.add_task(
            run_optimization_async,
            job_id,
            strategy_class,
            data,
            request,
            engine,
            db
        )

        return BacktestJobResponse(
            job_id=job_id,
            status=BacktestStatus.SUBMITTED,
            message="Optimization submitted successfully"
        )

    except Exception as e:
        logger.error(f"Error submitting optimization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Background task functions
async def run_backtest_async(
    job_id: str,
    strategy_class,
    data,
    request: BacktestRequest,
    engine: BacktestEngine,
    cache: BacktestCache,
    db: Session
):
    """Run backtest asynchronously."""
    try:
        # Update status to running
        backtest_run = db.query(BacktestRun).filter(BacktestRun.id == job_id).first()
        backtest_run.status = 'running'
        db.commit()

        # Run backtest
        result = engine.run_backtest(
            strategy_class=strategy_class,
            data=data,
            initial_capital=request.initial_capital,
            commission=request.commission,
            parameters=request.parameters
        )

        # Update database
        backtest_run.status = 'completed'
        backtest_run.final_capital = result['final_capital']
        backtest_run.total_return = result['metrics']['total_return']
        backtest_run.sharpe_ratio = result['metrics']['sharpe_ratio']
        backtest_run.max_drawdown = result['metrics']['max_drawdown']
        backtest_run.total_trades = result['metrics']['total_trades']
        backtest_run.win_rate = result['metrics']['win_rate']
        backtest_run.execution_time = result['execution_time']
        backtest_run.full_results = result
        db.commit()

        # Cache result
        cache.cache_backtest_result(
            strategy=request.strategy.value,
            symbol=request.symbol,
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            parameters=request.parameters,
            result=result
        )

        logger.info(f"Backtest {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Backtest {job_id} failed: {e}", exc_info=True)
        backtest_run = db.query(BacktestRun).filter(BacktestRun.id == job_id).first()
        backtest_run.status = 'failed'
        backtest_run.error_message = str(e)
        db.commit()


async def run_optimization_async(
    job_id: str,
    strategy_class,
    data,
    request: OptimizationRequest,
    engine: BacktestEngine,
    db: Session
):
    """Run optimization asynchronously."""
    try:
        logger.info(f"Starting optimization {job_id}")

        result = engine.optimize_parameters(
            strategy_class=strategy_class,
            data=data,
            parameter_grid=request.parameter_grid,
            optimization_metric=request.optimization_metric,
            initial_capital=request.initial_capital,
            commission=0.001
        )

        # Store in database (create OptimizationRun table entry)
        logger.info(f"Optimization {job_id} completed")

    except Exception as e:
        logger.error(f"Optimization {job_id} failed: {e}", exc_info=True)


from uuid import uuid4
