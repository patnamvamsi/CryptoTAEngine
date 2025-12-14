# Database Consolidation: Single TimescaleDB

## 🎯 Overview

The system has been simplified to use **only TimescaleDB** instead of separate PostgreSQL and TimescaleDB instances.

**Why this works:**
- TimescaleDB is built on PostgreSQL (it's PostgreSQL + time-series extensions)
- It can handle **both** regular relational tables AND time-series data
- Reduces complexity, resource usage, and management overhead

---

## 🔄 What Changed

### Before (2 Databases)
```yaml
services:
  postgres:           # Port 5432 - For backtest results, trades, etc.
  timescaledb:        # Port 5433 - For OHLCV time series data
  redis:              # Port 6379 - For caching
```

### After (1 Database + Redis)
```yaml
services:
  timescaledb:        # Port 5432 - For EVERYTHING (regular + time series)
  redis:              # Port 6379 - For caching
```

---

## 📊 Database Schema

### Single Database: `trading_engine`

The TimescaleDB instance now contains both types of tables:

#### Regular Tables (PostgreSQL functionality)
- `backtest_runs` - Backtest execution results
- `optimization_runs` - Parameter optimization results
- `live_trades` - Live trading records
- `data_cache` - Historical data cache metadata

#### Hypertables (TimescaleDB functionality)
- `ohlcv` - Time-series OHLCV candlestick data
  - Automatically partitioned by time
  - Optimized for time-based queries
  - Supports continuous aggregates

---

## 🔧 Configuration Changes

### Environment Variables (Simplified)

**Before:**
```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=trading_engine

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres
TIMESCALE_DB=timeseries_data
```

**After:**
```bash
# Single TimescaleDB (handles everything)
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5432
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres
TIMESCALE_DB=trading_engine
```

### Code Configuration

In `app/core/config.py`:

```python
@property
def DATABASE_URL(self) -> str:
    """Uses TimescaleDB for both regular tables and time series data."""
    return f"postgresql://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"

@property
def TIMESCALE_URL(self) -> str:
    """Alias for DATABASE_URL - same database handles both."""
    return self.DATABASE_URL
```

Both `DATABASE_URL` and `TIMESCALE_URL` now point to the same database!

---

## 🐳 Docker Compose Changes

### Services Reduced
- **Removed:** `postgres` service (port 5432)
- **Updated:** `timescaledb` service now on port 5432
- **Kept:** All other services (api, celery_worker, celery_beat, flower, redis)

### Volume Changes
```yaml
volumes:
  timescale_data:  # Single volume for all data
  redis_data:      # Redis cache
  # Removed: postgres_data
```

### Resource Savings
- **Memory:** ~500MB saved (one less PostgreSQL instance)
- **Storage:** Consolidated into single volume
- **Network:** Fewer inter-service connections
- **Complexity:** Simpler dependency graph

---

## 🚀 Getting Started

### Quick Start (Docker Compose)

```bash
# 1. Create environment file
cp .env.template .env

# 2. Edit .env - only need TimescaleDB settings now
nano .env

# 3. Start services (now only 5 containers instead of 6)
docker-compose up -d

# 4. Verify services
docker-compose ps
```

Expected output:
```
NAME                     STATUS
cryptota_timescale       Up (healthy)  # Only one database!
cryptota_redis           Up (healthy)
cryptota_api             Up
cryptota_celery_worker   Up
cryptota_celery_beat     Up
cryptota_flower          Up
```

### Manual Setup

```bash
# 1. Start TimescaleDB
docker run -d \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=trading_engine \
  -v timescale_data:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg15

# 2. Create tables
cd app
python -c "
from data.storage.database import db_manager
from data.storage.timeseries import timeseries_db

# Initialize and create regular tables
db_manager.initialize()
db_manager.create_tables()

# Create hypertables for time series
timeseries_db.initialize()
timeseries_db.create_hypertable()
"
```

---

## 📊 Database Operations

### Connect to Database

```bash
# Via Docker
docker exec -it cryptota_timescale psql -U postgres -d trading_engine

# Direct connection
psql -h localhost -U postgres -d trading_engine
```

### Verify Tables

```sql
-- List all tables
\dt

-- Expected output:
--  Schema |      Name        | Type  |  Owner
-- --------+------------------+-------+----------
--  public | backtest_runs    | table | postgres
--  public | optimization_runs| table | postgres
--  public | live_trades      | table | postgres
--  public | data_cache       | table | postgres
--  public | ohlcv            | table | postgres  (hypertable)

-- Check TimescaleDB hypertables
SELECT * FROM timescaledb_information.hypertables;

-- Should show 'ohlcv' as a hypertable
```

### Query Examples

```sql
-- Regular table query (backtest results)
SELECT strategy, symbol, total_return, sharpe_ratio
FROM backtest_runs
ORDER BY created_at DESC
LIMIT 10;

-- Time-series query (OHLCV data)
SELECT time, symbol, close, volume
FROM ohlcv
WHERE symbol = 'BTCUSDT'
  AND time >= NOW() - INTERVAL '7 days'
ORDER BY time DESC;

-- Aggregated time-series (TimescaleDB feature)
SELECT
  time_bucket('1 hour', time) AS hour,
  symbol,
  FIRST(open, time) AS open,
  MAX(high) AS high,
  MIN(low) AS low,
  LAST(close, time) AS close,
  SUM(volume) AS volume
FROM ohlcv
WHERE symbol = 'BTCUSDT'
  AND time >= NOW() - INTERVAL '1 day'
GROUP BY hour, symbol
ORDER BY hour DESC;
```

---

## 🎯 Benefits of Single Database

### 1. **Simplified Architecture**
- One database to manage instead of two
- Single connection pool
- Unified backup/restore process
- Easier monitoring

### 2. **Reduced Resource Usage**
- ~500MB less memory (one PostgreSQL instance instead of two)
- Single storage volume
- Fewer Docker containers
- Lower CPU overhead

### 3. **Better Performance**
- No cross-database queries needed
- Can join regular tables with time-series data
- Shared connection pool optimization
- Better cache utilization

### 4. **Cost Savings**
- 50% fewer database instances in production
- Simplified cloud deployment (one RDS/Cloud SQL instance)
- Reduced backup storage costs

### 5. **Operational Simplicity**
- Single database to monitor
- One connection string
- Unified maintenance window
- Simpler disaster recovery

---

## 🔄 Migration from Old Setup

### If You Had Separate Databases

```bash
# 1. Stop services
docker-compose down

# 2. Backup data (if you have existing data)
docker exec cryptota_postgres pg_dump -U postgres trading_engine > backup_regular.sql
docker exec cryptota_timescale pg_dump -U postgres timeseries_data > backup_timeseries.sql

# 3. Update configuration files (already done)
# - docker-compose.yml
# - .env.template
# - app/core/config.py

# 4. Start new setup
docker-compose up -d

# 5. Restore data to single database (if needed)
docker exec -i cryptota_timescale psql -U postgres -d trading_engine < backup_regular.sql
docker exec -i cryptota_timescale psql -U postgres -d trading_engine < backup_timeseries.sql
```

### Fresh Installation

```bash
# Just follow the normal setup - everything is already configured!
cp .env.template .env
docker-compose up -d
```

---

## 🧪 Testing the Setup

### 1. Verify TimescaleDB Extension

```sql
-- Connect to database
psql -h localhost -U postgres -d trading_engine

-- Check TimescaleDB is installed
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';

-- Should return:
--   extname   | extversion
-- ------------+------------
--  timescaledb | 2.x.x
```

### 2. Test Regular Tables

```python
from data.storage.database import db_manager, BacktestRun
from datetime import datetime

db_manager.initialize()

with db_manager.get_session() as session:
    # Create test backtest
    test_run = BacktestRun(
        id='test-123',
        strategy='rsi',
        symbol='BTCUSDT',
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 12, 31),
        timeframe='15m',
        initial_capital=10000.0,
        status='completed'
    )
    session.add(test_run)
    session.commit()

    # Query it back
    result = session.query(BacktestRun).filter_by(id='test-123').first()
    print(f"Found: {result.strategy} on {result.symbol}")
```

### 3. Test Time-Series Data

```python
from data.storage.timeseries import timeseries_db
import pandas as pd
from datetime import datetime, timedelta

# Initialize
timeseries_db.initialize()
timeseries_db.create_hypertable()

# Create test OHLCV data
data = pd.DataFrame({
    'timestamp': pd.date_range(start='2023-01-01', periods=100, freq='15T'),
    'open': 45000.0,
    'high': 45100.0,
    'low': 44900.0,
    'close': 45050.0,
    'volume': 1000.0,
    'trades': 100,
    'quote_volume': 45000000.0
})

# Insert data
timeseries_db.insert_ohlcv(data, 'BTCUSDT', '15m')

# Query it back
result = timeseries_db.query_ohlcv(
    'BTCUSDT',
    datetime(2023, 1, 1),
    datetime(2023, 1, 2),
    '15m'
)
print(f"Retrieved {len(result)} candles")
```

---

## 📚 Additional Resources

### TimescaleDB Documentation
- [TimescaleDB Overview](https://docs.timescale.com/)
- [Hypertables](https://docs.timescale.com/use-timescale/latest/hypertables/)
- [Continuous Aggregates](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/)
- [Time Series Best Practices](https://docs.timescale.com/timescaledb/latest/how-to-guides/query-data/advanced-analytic-queries/)

### PostgreSQL Compatibility
- TimescaleDB is 100% PostgreSQL compatible
- All PostgreSQL features work normally
- Can use any PostgreSQL tool (pgAdmin, DBeaver, etc.)
- Standard SQL queries work as expected

---

## 🎓 Summary

**Before:** 2 databases (PostgreSQL + TimescaleDB)
**After:** 1 database (TimescaleDB only)

**Result:**
✅ Simpler architecture
✅ Reduced resource usage (~500MB memory saved)
✅ Easier to manage and monitor
✅ Same functionality, better performance
✅ Lower operational costs

**No functionality lost** - TimescaleDB does everything PostgreSQL does, plus advanced time-series features!

---

## 📞 Troubleshooting

### Issue: "Could not connect to database"

```bash
# Check if TimescaleDB is running
docker ps | grep timescale

# Check logs
docker logs cryptota_timescale

# Verify port
docker port cryptota_timescale
```

### Issue: "TimescaleDB extension not found"

```sql
-- Manually create extension if needed
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

### Issue: "Hypertable already exists"

This is normal - the setup is idempotent. The system checks before creating.

---

**Migration Complete!** You now have a simplified, efficient single-database architecture. 🎉
