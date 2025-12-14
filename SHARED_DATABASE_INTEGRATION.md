# Shared TimescaleDB Integration with CryptoMarketData

## 🎯 Overview

CryptoTAEngine now integrates with the **CryptoMarketData** microservice by sharing the same TimescaleDB instance. This eliminates data duplication and provides access to real-time market data from multiple exchanges.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│           TimescaleDB (market_data database)             │
│                                                          │
│  ┌────────────────────┐    ┌────────────────────┐      │
│  │  Regular Tables     │    │   Hypertables      │      │
│  │  (CryptoTAEngine)   │    │  (CryptoMarketData)│      │
│  │                     │    │                    │      │
│  │ - backtest_runs     │    │ - binance_*_kline_*│      │
│  │ - optimization_runs │    │ - zerodha_*_kline_*│      │
│  │ - live_trades       │    │ - symbols          │      │
│  │ - data_cache        │    │ - binance_symbols  │      │
│  └────────────────────┘    └────────────────────┘      │
└─────────────────────────────────────────────────────────┘
         ▲                           ▲
         │                           │
  ┌──────┴──────┐            ┌──────┴──────┐
  │ CryptoTA    │            │ CryptoMarket│
  │ Engine      │            │ Data        │
  │ (Port 8001) │            │ (Port 8002) │
  └─────────────┘            └─────────────┘
```

---

## 📊 Database Schema

### Database: `market_data`

#### Tables Managed by CryptoTAEngine
```sql
-- Backtest execution results
backtest_runs

-- Parameter optimization results
optimization_runs

-- Live trading records
live_trades

-- Data cache metadata
data_cache
```

#### Tables Managed by CryptoMarketData
```sql
-- Symbol information
symbols
binance_symbols

-- OHLCV time-series data (one table per symbol/interval)
binance_btcusdt_kline_1m
binance_btcusdt_kline_5m
binance_ethusdt_kline_1m
zerodha_reliance_kline_1m
zerodha_tcs_kline_1h
... (and many more)
```

---

## 🔌 Data Access

### Using the Shared Data Provider

```python
from data.providers.shared_timescale_provider import shared_timescale_provider

# Fetch Binance OHLCV data
btc_data = shared_timescale_provider.fetch_ohlcv(
    symbol='BTCUSDT',
    exchange='binance',
    timeframe='1m',
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31),
    limit=10000
)

# Fetch Zerodha/NSE data
reliance_data = shared_timescale_provider.fetch_ohlcv(
    symbol='RELIANCE',
    exchange='zerodha',
    timeframe='1m',
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Get available symbols
binance_symbols = shared_timescale_provider.get_available_symbols(
    exchange='binance',
    active_only=True
)

# Check if data exists
exists = shared_timescale_provider.check_table_exists(
    exchange='binance',
    symbol='BTCUSDT',
    timeframe='1m'
)

# Get data summary
summary = shared_timescale_provider.get_data_summary(
    exchange='binance',
    symbol='BTCUSDT',
    timeframe='1m'
)
```

### Direct SQL Queries

```python
from data.storage.timeseries import timeseries_db
import pandas as pd
from sqlalchemy import text

# Connect to shared database
timeseries_db.initialize()

# Query Binance data
query = """
SELECT open_time as timestamp, open, high, low, close, volume
FROM binance_btcusdt_kline_1m
WHERE open_time >= NOW() - INTERVAL '7 days'
ORDER BY open_time ASC
"""

df = pd.read_sql(text(query), timeseries_db.engine)

# Query Zerodha data
query = """
SELECT open_time as timestamp, open, high, low, close, volume
FROM zerodha_reliance_kline_1m
WHERE open_time >= NOW() - INTERVAL '1 day'
ORDER BY open_time ASC
"""

df = pd.read_sql(text(query), timescales_db.engine)
```

---

## 🚀 Setup Instructions

### Prerequisites
1. **CryptoMarketData** microservice must be running
2. **TimescaleDB** instance must be accessible (port 5432)
3. **market_data** database must exist and be populated

### Configuration

#### 1. Environment Variables (`.env`)

```bash
# TimescaleDB (shared with CryptoMarketData)
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=your_password
TIMESCALE_HOST=localhost  # or IP address of TimescaleDB server
TIMESCALE_PORT=5432
TIMESCALE_DB=market_data  # IMPORTANT: Must be 'market_data'
```

#### 2. Docker Deployment

The Docker Compose file uses `host.docker.internal` to access the host's TimescaleDB:

```yaml
environment:
  TIMESCALE_HOST: host.docker.internal
  TIMESCALE_PORT: 5432
  TIMESCALE_DB: market_data
```

#### 3. Verify Connection

```bash
# Test database connection
psql -h localhost -U postgres -d market_data -c "\dt"

# Should show tables from both microservices:
# - binance_symbols, symbols (from CryptoMarketData)
# - backtest_runs, live_trades (from CryptoTAEngine)
# - binance_*_kline_* tables (from CryptoMarketData)
```

---

## 📋 Table Naming Convention

### CryptoMarketData Tables

**Pattern:** `{exchange}_{symbol}_kline_{interval}`

**Examples:**
```
Binance:
- binance_btcusdt_kline_1m
- binance_btcusdt_kline_5m
- binance_btcusdt_kline_15m
- binance_ethusdt_kline_1m
- binance_bnbusdt_kline_1h

Zerodha/NSE:
- zerodha_reliance_kline_1m
- zerodha_tcs_kline_1m
- zerodha_hdfcbank_kline_5m
- zerodha_infy_kline_1h
```

**Symbols are lowercase:** `BTCUSDT` → `btcusdt`, `RELIANCE` → `reliance`

### Column Schema (OHLCV Tables)

```sql
CREATE TABLE {exchange}_{symbol}_kline_{interval} (
    open_time TIMESTAMPTZ PRIMARY KEY,  -- Candle open time (UTC)
    open NUMERIC,                       -- Opening price
    high NUMERIC,                       -- Highest price
    low NUMERIC,                        -- Lowest price
    close NUMERIC,                      -- Closing price
    volume NUMERIC,                     -- Base asset volume
    close_time TIMESTAMPTZ,             -- Candle close time
    quote_asset_volume NUMERIC,         -- Quote asset volume
    trades NUMERIC,                     -- Number of trades
    taker_buy_base_asset_volume NUMERIC,
    taker_buy_quote_asset_volume NUMERIC,
    ignore NUMERIC
);

-- TimescaleDB hypertable (automatically partitioned by time)
SELECT create_hypertable('{table_name}', 'open_time');
```

---

## 🔄 Data Flow

### Historical Backtesting

```
1. User submits backtest request
   ↓
2. CryptoTAEngine fetches data from shared TimescaleDB
   ↓
3. Query: binance_btcusdt_kline_1m (populated by CryptoMarketData)
   ↓
4. Run backtest with fetched data
   ↓
5. Store results in backtest_runs table (CryptoTAEngine)
```

### Real-Time Data Access

```
CryptoMarketData (continuous):
- WebSocket → Binance/Zerodha
- Insert to TimescaleDB
- Tables updated in real-time

CryptoTAEngine (on-demand):
- Query latest data from TimescaleDB
- Always up-to-date (no staleness)
- No need to fetch from exchange APIs
```

---

## 🎯 Benefits of Shared Database

### 1. **No Data Duplication**
- Single source of truth for market data
- Reduced storage requirements
- Consistent data across microservices

### 2. **Real-Time Access**
- CryptoMarketData streams live data
- CryptoTAEngine always has latest candles
- No need for separate data fetching

### 3. **Multi-Exchange Support**
- Binance (crypto)
- Zerodha/NSE (Indian stocks)
- Easy to add more exchanges

### 4. **Historical Data**
- Years of historical data (depending on CryptoMarketData setup)
- No need to download again
- Gap filling handled by CryptoMarketData

### 5. **Resource Efficiency**
- One TimescaleDB instance instead of two
- Shared connection pool
- Reduced memory and CPU usage

---

## 📚 Available Data

### Binance (Crypto)

**Supported Intervals:**
- 1m, 3m, 5m, 15m, 30m
- 1h, 2h, 4h, 6h, 8h, 12h
- 1d, 3d, 1w, 1M

**Symbols:** All trading pairs (2000+)
- Check `binance_symbols` table for active symbols
- Priority field indicates importance

### Zerodha/NSE (Indian Stocks)

**Supported Intervals:**
- 1m, 3m, 5m, 10m, 15m, 30m
- 1h, 1d

**Default Symbols:**
- RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK
- HINDUNILVR, ITC, KOTAKBANK, LT, MARUTI
- SBIN, SUNPHARMA, TATAMOTORS, TATASTEEL, WIPRO

**Limitation:** Historical data limited to 60 days for minute-level

---

## 🧪 Testing the Integration

### 1. Verify Database Access

```python
from data.storage.timeseries import timeseries_db

# Initialize connection
timeseries_db.initialize()

# Test query
from sqlalchemy import text
result = timeseries_db.engine.execute(text("SELECT version()"))
print(result.fetchone())
```

### 2. List Available Tables

```python
query = """
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE '%kline%'
ORDER BY tablename
LIMIT 20;
"""

import pandas as pd
tables = pd.read_sql(text(query), timeseries_db.engine)
print(tables)
```

### 3. Fetch Sample Data

```python
from data.providers.shared_timescale_provider import shared_timescale_provider
from datetime import datetime, timedelta

# Get recent Bitcoin data
data = shared_timescale_provider.fetch_ohlcv(
    symbol='BTCUSDT',
    exchange='binance',
    timeframe='1m',
    start_date=datetime.now() - timedelta(hours=1),
    end_date=datetime.now(),
    limit=60
)

print(f"Fetched {len(data)} candles")
print(data.head())
print(data.tail())
```

### 4. Run Backtest with Shared Data

```python
from backtesting.engine import BacktestEngine
from strategies.rsi_strategy import RSIStrategy

# Fetch data from shared database
data = shared_timescale_provider.fetch_ohlcv(
    symbol='BTCUSDT',
    exchange='binance',
    timeframe='15m',
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Run backtest
engine = BacktestEngine()
result = engine.run_backtest(
    strategy_class=RSIStrategy,
    data=data,
    initial_capital=10000.0,
    commission=0.001
)

print(f"Total Return: {result['metrics']['total_return']:.2f}%")
print(f"Sharpe Ratio: {result['metrics']['sharpe_ratio']:.2f}")
```

---

## 🔒 Security Considerations

### Database Access
- Both microservices share same credentials
- Use strong password for TIMESCALE_PASSWORD
- Consider read-only user for CryptoTAEngine (only needs read access to OHLCV tables)

### Network Security
- TimescaleDB should not be exposed to public internet
- Use firewall rules to restrict access
- Consider VPN for remote access

### Backup Strategy
- CryptoMarketData should handle database backups
- Coordinate with CryptoMarketData team for backup schedules
- Test restore procedures

---

## 🛠️ Troubleshooting

### Issue: "Table does not exist"

**Cause:** Symbol/interval table not created by CryptoMarketData

**Solution:**
1. Check if symbol is active in CryptoMarketData
2. Trigger data fetch via CryptoMarketData API:
   ```bash
   curl "http://localhost:8002/update/marketdata/BTCUSDT"
   ```
3. Verify table exists:
   ```sql
   SELECT tablename FROM pg_tables
   WHERE tablename = 'binance_btcusdt_kline_1m';
   ```

### Issue: "Connection refused to TimescaleDB"

**Cause:** TimescaleDB not running or wrong connection settings

**Solution:**
1. Verify TimescaleDB is running:
   ```bash
   psql -h localhost -U postgres -d market_data -c "SELECT 1"
   ```
2. Check TIMESCALE_HOST in .env
3. For Docker: Use `host.docker.internal` instead of `localhost`

### Issue: "No data returned"

**Cause:** Requested time range has no data

**Solution:**
1. Check latest timestamp:
   ```python
   latest = shared_timescale_provider.get_latest_timestamp(
       exchange='binance',
       symbol='BTCUSDT',
       timeframe='1m'
   )
   print(f"Latest data: {latest}")
   ```
2. Adjust date range or trigger gap fill in CryptoMarketData

### Issue: "Permission denied"

**Cause:** Database user doesn't have access to tables

**Solution:**
```sql
-- Grant read access to all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO postgres;

-- Grant access to future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO postgres;
```

---

## 📞 Integration Checklist

Before running CryptoTAEngine with shared database:

- [ ] CryptoMarketData microservice is running
- [ ] TimescaleDB instance is accessible (test with psql)
- [ ] Database `market_data` exists
- [ ] TIMESCALE_PASSWORD is set correctly in .env
- [ ] Can query OHLCV tables (test with SQL)
- [ ] SharedTimescaleProvider can fetch data (test in Python)
- [ ] Backtest tables created (backtest_runs, etc.)
- [ ] Redis is running for caching

---

## 🎓 Summary

**What Changed:**
- Database name: `trading_engine` → `market_data` (shared)
- Data source: Binance API → Shared TimescaleDB
- OHLCV tables: Created by us → Created by CryptoMarketData
- Real-time data: Need to fetch → Always available

**What Stayed the Same:**
- All backtesting functionality
- Performance metrics calculation
- API endpoints
- Celery distributed processing

**Integration Points:**
1. **Data Reading:** SharedTimescaleProvider
2. **Database:** Same `market_data` instance
3. **Tables:** Read OHLCV, Write backtest results
4. **No conflicts:** Different table sets, shared database

**Result:** Efficient, integrated microservice architecture with shared data layer!

---

**Last Updated:** December 14, 2025
**Database:** market_data (shared with CryptoMarketData)
**Port:** 5432
