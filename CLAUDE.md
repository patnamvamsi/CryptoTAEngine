# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CryptoTAEngine is a distributed cryptocurrency backtesting and trading engine built with FastAPI, Celery, and TimescaleDB. It integrates with the CryptoMarketData microservice for real-time and historical OHLCV data. The system uses Backtrader for backtesting with custom strategy base classes and comprehensive performance metrics.

## Essential Commands

### Development Setup

```bash
# Create environment file
cp .env.template .env
# Edit .env with your Binance API credentials and database settings

# Install dependencies
pip install -r requirements.txt
```

### Running Services

```bash
# Start all services (Docker Compose - recommended)
docker-compose up -d

# Start API only (local development)
uvicorn app.main_new:app --reload --port 8001

# Start Celery worker (separate terminal, from app/ directory)
cd app
celery -A celery_app worker --loglevel=info --concurrency=4

# Start Celery beat scheduler (optional, separate terminal)
cd app
celery -A celery_app beat --loglevel=info

# Monitor Celery tasks via Flower
# Available at http://localhost:5555 when using docker-compose
```

### Testing & Development

```bash
# API documentation (when server is running)
# http://localhost:8001/docs

# Health check
curl http://localhost:8001/health

# Run a simple backtest (example)
curl -X POST "http://localhost:8001/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "rsi",
    "symbol": "BTCUSDT",
    "start_date": "2023-01-01T00:00:00",
    "end_date": "2023-01-31T23:59:59",
    "timeframe": "15m",
    "initial_capital": 10000.0
  }'

# Check logs
docker-compose logs -f api
docker-compose logs -f celery_worker
```

### Database Operations

```bash
# Connect to TimescaleDB (shared with CryptoMarketData)
docker exec -it cryptota_postgres psql -U postgres -d market_data

# View backtest results
# SELECT id, strategy, symbol, total_return, sharpe_ratio FROM backtest_runs LIMIT 10;

# Initialize/create database tables (if needed)
cd app
python -c "from data.storage.database import db_manager; db_manager.initialize(); db_manager.create_tables()"
```

## Architecture Overview

### Core Components

**FastAPI Application** (`app/main_new.py`)
- Main entry point with lifespan management
- Initializes database, TimescaleDB, and Redis on startup
- Includes routers for backtest, health, and data endpoints
- CORS middleware configured for API access

**Celery Distributed Processing** (`app/celery_app.py`)
- Handles asynchronous backtest execution via Redis
- Task serialization using pickle for complex objects
- 1-hour time limit per backtest task
- Worker prefetch multiplier set to 1 for optimal distribution

**Configuration Management** (`app/core/config.py`)
- Pydantic-based settings loaded from environment variables
- Supports .env file with fallback defaults
- Centralizes all configuration (API, database, Redis, Celery, backtesting parameters)
- Property-based URL construction for databases

### Data Architecture

**TimescaleDB Integration** (`app/data/providers/shared_timescale_provider.py`)
- Connects to CryptoMarketData's existing TimescaleDB instance (shared database)
- Reads from pre-populated tables: `{exchange}_{symbol}_kline_{interval}`
  - Example: `binance_btcusdt_kline_1m`, `zerodha_reliance_kline_1h`
- No data duplication - leverages existing market data infrastructure
- Supports both Binance and Zerodha exchanges
- Provides OHLCV queries with flexible date range filtering

**Database Models** (`app/data/storage/database.py`)
- SQLAlchemy ORM models for backtest results and metadata
- Stores backtest runs, metrics, trades, and optimization results
- Separate from TimescaleDB - uses PostgreSQL for structured data

**Redis Caching** (`app/utils/cache.py`)
- Caches backtest results to avoid re-running identical tests
- 24-hour default TTL configurable via CACHE_TTL env var
- Key format includes strategy, symbol, dates, and parameters for uniqueness

### Strategy System

**Base Strategy Classes** (`app/strategies/base.py`)
- `BaseStrategy`: Abstract base class with template pattern
  - `setup_indicators()`: Override to define technical indicators
  - `generate_signals()`: Override to implement trading logic (returns {'buy': bool, 'sell': bool})
  - Automatic trade tracking, order management, and portfolio monitoring
- `LongOnlyStrategy`: Extends BaseStrategy for long-only trades
- `LongShortStrategy`: Extends BaseStrategy for long/short trades

**Creating Custom Strategies**
1. Inherit from `LongOnlyStrategy` or `LongShortStrategy`
2. Define strategy parameters as class-level `params` tuple
3. Implement `setup_indicators()` to create indicators
4. Implement `generate_signals()` to return buy/sell signals
5. Optionally override `calculate_position_size()` for custom sizing
6. Register in `app/api/routes/backtest.py` STRATEGY_MAP dictionary

### Backtesting Engine

**BacktestEngine** (`app/backtesting/engine.py`)
- Uses custom Cerebro class for non-blocking plot generation
- Supports single backtests, parameter optimization (grid search), and walk-forward analysis
- Parallel execution using ProcessPoolExecutor for parameter optimization
- Returns comprehensive metrics from PerformanceMetrics.calculate_all()
- Generates interactive Plotly charts from Backtrader plots

**Performance Metrics** (`app/backtesting/metrics.py`)
- 30+ performance indicators including:
  - Returns: total_return, annual_return, CAGR
  - Risk: volatility, max_drawdown, VaR, CVaR
  - Risk-adjusted: sharpe_ratio, sortino_ratio, calmar_ratio
  - Trading: win_rate, profit_factor, avg_win, avg_loss
  - Benchmark: alpha, beta, information_ratio (if benchmark provided)

## Integration with CryptoMarketData

This microservice depends on the CryptoMarketData service for market data:

**Database Connection**
- Uses shared TimescaleDB instance (database: `market_data`)
- Connection configured via TIMESCALE_* environment variables
- In Docker: use `host.docker.internal` to access host's TimescaleDB
- CryptoMarketData must be running and populating data before backtests

**Table Structure**
- Tables follow pattern: `{exchange}_{symbol}_kline_{interval}`
- Columns: open_time, open, high, low, close, volume, trades, quote_asset_volume
- Data continuously updated by CryptoMarketData's WebSocket streams
- Supports multiple exchanges: Binance, Zerodha

**Data Flow**
1. CryptoMarketData streams real-time data from exchanges → TimescaleDB
2. CryptoTAEngine queries TimescaleDB for historical ranges
3. Backtests run on queried data with Backtrader
4. Results stored in separate PostgreSQL database (not TimescaleDB)

## Docker Compose Architecture

**Services Included**
- `redis`: Caching and Celery broker (port 6379)
- `api`: FastAPI application (port 8001)
- `celery_worker`: Background task processing
- `celery_beat`: Scheduled task execution
- `flower`: Celery monitoring UI (port 5555)

**Important Notes**
- TimescaleDB is NOT in this compose file - managed by CryptoMarketData
- Services use `host.docker.internal` to access host's TimescaleDB
- Environment variables passed via docker-compose.yml and .env file
- Volumes mounted for code hot-reloading in development

## File Organization

```
app/
├── api/
│   ├── routes/          # API endpoints (backtest, health, data)
│   └── dependencies.py  # FastAPI dependency injection
├── core/
│   ├── config.py        # Pydantic settings from environment
│   ├── models.py        # Pydantic request/response models
│   └── exceptions.py    # Custom exception classes
├── strategies/
│   ├── base.py          # Abstract strategy base classes
│   └── rsi_strategy.py  # RSI strategy implementations
├── backtesting/
│   ├── engine.py        # Backtesting engine with optimization
│   ├── metrics.py       # Performance metric calculations
│   └── tasks.py         # Celery background tasks
├── data/
│   ├── providers/
│   │   ├── binance_provider.py           # Binance API client
│   │   └── shared_timescale_provider.py  # TimescaleDB queries
│   └── storage/
│       ├── database.py  # PostgreSQL ORM models
│       └── timeseries.py # TimescaleDB connection
├── utils/
│   ├── cache.py         # Redis caching utilities
│   └── logging_config.py # Structured logging setup
├── main_new.py          # FastAPI application entry point
└── celery_app.py        # Celery configuration
```

## Code Patterns & Conventions

**Dependency Injection**
- All database sessions, engines, and providers use FastAPI's Depends()
- Defined in `app/api/dependencies.py`
- Ensures proper resource lifecycle and testability

**Error Handling**
- Custom exceptions in `app/core/exceptions.py`: BacktestError, DataFetchError, etc.
- API routes return HTTPException with appropriate status codes
- Comprehensive logging at all layers (logger.info, logger.error with exc_info=True)

**Logging**
- Structured JSON logging configured in utils/logging_config.py
- Log level controlled by LOG_LEVEL environment variable
- Format controlled by LOG_FORMAT (json or console)

**Configuration**
- All hardcoded values replaced with environment variables
- Use `from core.config import settings` to access configuration
- Never commit sensitive values - use .env.template as reference

**Async Patterns**
- API endpoints are async def for FastAPI
- Background tasks use Celery, not FastAPI's BackgroundTasks for long-running operations
- Database queries are synchronous (SQLAlchemy ORM)

## Common Development Tasks

**Adding a New Strategy**
1. Create file in `app/strategies/your_strategy.py`
2. Inherit from LongOnlyStrategy or LongShortStrategy
3. Implement setup_indicators() and generate_signals()
4. Add to STRATEGY_MAP in `app/api/routes/backtest.py`
5. Test via POST /backtest/run with strategy name

**Modifying Backtest Metrics**
- Edit `app/backtesting/metrics.py`
- Update PerformanceMetrics.calculate_all() method
- New metrics automatically included in API responses

**Changing Database Schema**
- Update SQLAlchemy models in `app/data/storage/database.py`
- Consider using Alembic for migrations in production
- Re-run create_tables() for development

**Accessing Different Exchange Data**
- Use shared_timescale_provider.fetch_ohlcv(exchange='binance'|'zerodha')
- Ensure CryptoMarketData is configured for that exchange
- Check table exists with check_table_exists() method

## Migration from v1.0 to v2.0

See MIGRATION_GUIDE.md for detailed migration instructions. Key changes:
- API endpoints changed from GET to POST with async job submission
- Hardcoded paths replaced with environment variables
- New database layer with PostgreSQL and TimescaleDB separation
- Grid bot bug fixed (line 97 - order_limit_sell → order_limit_buy)
- Response format now includes comprehensive metrics, not just HTML

## Known Issues & Limitations

**Current Limitations**
- Walk-forward analysis optimization not fully implemented (marked TODO in engine.py line 318)
- Plot generation may fail silently - check logs if plot_html is None
- Parameter optimization uses ProcessPoolExecutor - may be memory-intensive for large grids

**Performance Considerations**
- TimescaleDB queries are fast but large date ranges may be slow
- Cache aggressively using Redis to avoid re-running identical backtests
- Parameter optimization scales with n_workers (default: min(CPU_count, 10))
- For very large optimizations, consider using vectorbt instead of Backtrader

## Environment Variables Reference

Critical variables (see .env.template for full list):
- `TIMESCALE_HOST`: TimescaleDB host (use `host.docker.internal` in Docker)
- `TIMESCALE_PORT`, `TIMESCALE_USER`, `TIMESCALE_PASSWORD`, `TIMESCALE_DB`
- `BINANCE_API_KEY`, `BINANCE_API_SECRET`: Required for fetching new data
- `REDIS_HOST`, `REDIS_PORT`: Cache and Celery broker
- `INITIAL_CAPITAL`, `COMMISSION`: Default backtest parameters
- `MAX_PARALLEL_BACKTESTS`: Limit concurrent optimization jobs
