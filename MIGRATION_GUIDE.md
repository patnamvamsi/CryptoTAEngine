# Migration Guide: v1.0 → v2.0

This guide helps you migrate from the old architecture to the new production-ready system.

---

## 🔄 Migration Strategy

You have **two options**:

### Option A: Fresh Start (Recommended)
Start using the new system alongside the old one, then gradually migrate.

### Option B: Replace Directly
Replace the old system entirely (requires more testing).

---

## 📝 Step-by-Step Migration (Option A - Recommended)

### Step 1: Set Up New Environment

```bash
# 1. Create environment file
cp .env.template .env

# 2. Edit .env and add your settings
nano .env  # or your preferred editor

# Required settings:
# - BINANCE_API_KEY
# - BINANCE_API_SECRET
# - Database credentials (if not using defaults)
```

### Step 2: Start New Services

```bash
# Start all services with Docker Compose
docker-compose up -d

# Verify all services are running
docker-compose ps

# Expected output:
# NAME                     STATUS
# cryptota_postgres        Up (healthy)
# cryptota_timescale       Up (healthy)
# cryptota_redis           Up (healthy)
# cryptota_api             Up
# cryptota_celery_worker   Up
# cryptota_celery_beat     Up
# cryptota_flower          Up
```

### Step 3: Test New API

```bash
# Test health endpoint
curl http://localhost:8001/health

# Test backtest submission
curl -X POST "http://localhost:8001/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "rsi",
    "symbol": "BTCUSDT",
    "start_date": "2023-01-01T00:00:00",
    "end_date": "2023-01-31T23:59:59",
    "timeframe": "15m",
    "initial_capital": 10000.0,
    "parameters": {
      "rsi_period": 14,
      "oversold": 30,
      "overbought": 70
    }
  }'
```

### Step 4: Parallel Running

Run both systems in parallel during testing:

**Old system** (main.py): http://localhost:8001
**New system** (main_new.py): http://localhost:8002

```yaml
# Modify docker-compose.yml temporarily:
services:
  api:
    ports:
      - "8002:8001"  # Map to different port
    # ...
```

### Step 5: Migrate Data (If Needed)

If you have existing backtest results to migrate:

```python
# migration_script.py
from data.storage.database import db_manager, BacktestRun
from datetime import datetime
import json

db_manager.initialize()

# Example: Import old results
old_results = [
    # Your old backtest results
]

with db_manager.get_session() as session:
    for result in old_results:
        backtest = BacktestRun(
            id=result['id'],
            strategy=result['strategy'],
            symbol=result['symbol'],
            start_date=datetime.fromisoformat(result['start_date']),
            end_date=datetime.fromisoformat(result['end_date']),
            # ... map other fields
        )
        session.add(backtest)
```

### Step 6: Update Clients

Update any clients calling your API:

**Before:**
```python
response = requests.get("http://localhost:8001/RSIbacktest")
html = response.json()
```

**After:**
```python
# Submit backtest
response = requests.post("http://localhost:8001/backtest/run", json={
    "strategy": "rsi",
    "symbol": "BTCUSDT",
    "start_date": "2023-01-01T00:00:00",
    "end_date": "2023-12-31T23:59:59",
    "timeframe": "15m",
    "initial_capital": 10000.0
})
job_id = response.json()['job_id']

# Get results
result = requests.get(f"http://localhost:8001/backtest/{job_id}/results").json()
metrics = result['metrics']
html_plot = result['plot_html']
```

### Step 7: Switch Over

Once confident in the new system:

```bash
# Stop old system
# Update any reverse proxies/load balancers to point to new API
# Monitor logs for issues

docker-compose logs -f api
```

---

## 🗺️ Code Migration Map

### Old → New File Mappings

| Old File | New Location | Status |
|----------|--------------|--------|
| `main.py` | `main_new.py` | Completely rewritten |
| `RSI_strategy.py` | `strategies/rsi_strategy.py` | Refactored with base class |
| `grid_bot.py` | `grid_bot.py` | Bug fixed, kept in place |
| `Calculations.py` | `Calculations.py` | Kept as-is |
| N/A | `core/config.py` | NEW - Configuration |
| N/A | `core/models.py` | NEW - Data models |
| N/A | `backtesting/engine.py` | NEW - Backtesting engine |
| N/A | `backtesting/metrics.py` | NEW - Performance metrics |
| N/A | `data/storage/database.py` | NEW - Database layer |
| N/A | `utils/cache.py` | NEW - Caching layer |

### API Endpoint Changes

| Old Endpoint | New Endpoint | Method | Changes |
|--------------|--------------|--------|---------|
| `GET /` | `GET /` | GET | Enhanced with API info |
| `GET /RSIbacktest` | `POST /backtest/run` | POST | Async, configurable |
| `GET /backtest` | `POST /backtest/run` | POST | Now implemented |
| N/A | `GET /backtest/{job_id}/status` | GET | NEW - Track progress |
| N/A | `GET /backtest/{job_id}/results` | GET | NEW - Get results |
| N/A | `POST /backtest/optimize` | POST | NEW - Optimization |
| N/A | `POST /data/fetch` | POST | NEW - Fetch historical |
| N/A | `GET /health` | GET | NEW - Health check |

---

## 🔧 Configuration Changes

### Old Way (Hardcoded)
```python
# In RSI_strategy.py
dataname='/home/vamsi/Dev/Projects/CryptoTrading/data/2020_15minutes.csv'
```

### New Way (Environment Variables)
```python
# In .env
BACKTEST_DATA_PATH=/data/2020_15minutes.csv

# In code (automatic)
from core.config import settings
data_path = settings.BACKTEST_DATA_PATH
```

---

## 🐛 Bug Fixes Applied

### 1. Grid Bot Bug (CRITICAL)

**Old code (line 97):**
```python
new_buy_order = client.order_limit_sell(...)  # WRONG!
```

**Fixed:**
```python
new_buy_order = client.order_limit_buy(...)  # CORRECT
```

### 2. Hardcoded Paths

**Old:**
```python
data = bt.feeds.GenericCSVData(
    dataname='/home/vamsi/Dev/Projects/CryptoTrading/data/2020_15minutes.csv',
    ...
)
```

**New:**
```python
from core.config import settings
data_path = os.getenv('BACKTEST_DATA_PATH', settings.BACKTEST_DATA_PATH)
data = bt.feeds.GenericCSVData(dataname=data_path, ...)
```

---

## 🎯 Feature Comparisons

### Backtesting

**v1.0:**
```python
# app/main.py
@app.get("/RSIbacktest")
def RSIbacktest():
    return RSI_strategy.get_backtest_results()
    # Returns only HTML plot
```

**v2.0:**
```python
# app/api/routes/backtest.py
@router.post("/run", response_model=BacktestJobResponse)
async def submit_backtest(request: BacktestRequest, ...):
    # - Validates input with Pydantic
    # - Checks cache first
    # - Runs in background with Celery
    # - Returns job_id immediately
    # - Stores results in database
    # - Returns 30+ metrics + plot
```

### Strategy Definition

**v1.0:**
```python
class RSIStrategy(bt.Strategy):
    def __init__(self):
        self.rsi = bt.talib.RSI(self.data, period=14)

    def next(self):
        if self.rsi < 30 and not self.position:
            self.buy(size=1)
        if self.rsi > 70 and self.position:
            self.close()
```

**v2.0:**
```python
from strategies.base import LongOnlyStrategy

class RSIStrategy(LongOnlyStrategy):
    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
    )

    def setup_indicators(self):
        self.rsi = bt.talib.RSI(self.data, period=self.params.rsi_period)

    def generate_signals(self) -> Dict[str, bool]:
        return {
            'buy': self.rsi[0] < self.params.oversold,
            'sell': self.rsi[0] > self.params.overbought
        }
    # Automatic trade logging, metrics, error handling
```

---

## ⚠️ Breaking Changes

### 1. API Response Format

**Old:**
```json
"<div>...</div>"  // Raw HTML string
```

**New:**
```json
{
  "job_id": "abc123",
  "strategy": "rsi",
  "metrics": {
    "total_return": 25.5,
    "sharpe_ratio": 1.45,
    ...
  },
  "trades": [...],
  "plot_html": "<div>...</div>"
}
```

### 2. Async Execution

**Old:** Synchronous (blocks until complete)
**New:** Asynchronous (returns job_id immediately)

Update client code to poll for completion:

```python
# Submit
response = requests.post('/backtest/run', json=request_data)
job_id = response.json()['job_id']

# Poll until complete
import time
while True:
    status = requests.get(f'/backtest/{job_id}/status').json()
    if status['status'] == 'completed':
        break
    time.sleep(2)

# Get results
results = requests.get(f'/backtest/{job_id}/results').json()
```

### 3. Configuration

**Old:** No configuration files
**New:** Requires `.env` file

---

## 🐳 Docker Migration

### Old Dockerfile (Simple)
```dockerfile
FROM python:3.8
WORKDIR /CryptoTAEngine/app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ .
CMD uvicorn main:app --host 0.0.0.0 --port 8001
```

### New Docker Compose (Multi-Service)
```yaml
services:
  postgres:      # Database for results
  timescaledb:   # Time series data
  redis:         # Cache & queue
  api:           # FastAPI app
  celery_worker: # Background processing
  celery_beat:   # Scheduled tasks
  flower:        # Monitoring
```

**Migration:** Use Docker Compose instead of standalone container

---

## 📊 Database Setup

The new system requires databases. Two options:

### Option 1: Docker Compose (Automatic)
```bash
docker-compose up -d
# All databases created automatically
```

### Option 2: Manual Setup
```bash
# PostgreSQL
createdb trading_engine

# TimescaleDB
createdb timeseries_data
psql timeseries_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Run from app/
python -c "from data.storage.database import db_manager; db_manager.initialize(); db_manager.create_tables()"
python -c "from data.storage.timeseries import timeseries_db; timeseries_db.initialize(); timeseries_db.create_hypertable()"
```

---

## 🧪 Testing the Migration

### 1. Test Health
```bash
curl http://localhost:8001/health
# Should return {"status": "healthy", ...}
```

### 2. Test Backtest
```bash
# Run simple backtest
curl -X POST http://localhost:8001/backtest/run \
  -H "Content-Type: application/json" \
  -d @test_backtest.json

# Check Celery is processing
# Visit http://localhost:5555 (Flower)
```

### 3. Test Data Fetching
```bash
curl -X POST http://localhost:8001/data/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "start_date": "2023-01-01T00:00:00",
    "end_date": "2023-01-07T00:00:00"
  }'
```

### 4. Test Database
```bash
docker exec -it cryptota_postgres psql -U postgres -d trading_engine

# Check tables
\dt

# Check backtest results
SELECT COUNT(*) FROM backtest_runs;
```

---

## 🚨 Rollback Plan

If you need to rollback to v1.0:

```bash
# 1. Stop new services
docker-compose down

# 2. Restart old service
uvicorn main:app --host 0.0.0.0 --port 8001

# 3. Your old code is still intact in:
#    - app/main.py
#    - app/RSI_strategy.py
#    - app/grid_bot.py (but keep the bug fix!)
```

---

## ✅ Migration Checklist

- [ ] Created `.env` file with all required variables
- [ ] Started Docker Compose services
- [ ] Verified all services are healthy
- [ ] Tested health endpoint
- [ ] Tested backtest submission
- [ ] Checked Flower for Celery tasks
- [ ] Verified database tables created
- [ ] Tested data fetching
- [ ] Updated client code for async API
- [ ] Migrated any existing data
- [ ] Updated documentation/wikis
- [ ] Notified team of API changes
- [ ] Set up monitoring/alerting
- [ ] Configured production environment variables
- [ ] Tested error scenarios
- [ ] Performed load testing

---

## 📞 Support

If you encounter issues during migration:

1. **Check logs:**
   ```bash
   docker-compose logs -f api
   docker-compose logs -f celery_worker
   ```

2. **Check service health:**
   ```bash
   curl http://localhost:8001/health
   ```

3. **Check Celery tasks:**
   Visit http://localhost:5555

4. **Check database:**
   ```bash
   docker exec -it cryptota_postgres psql -U postgres -d trading_engine
   ```

5. **Common issues:**
   - Missing `.env` file → Copy from `.env.template`
   - Port already in use → Change ports in `docker-compose.yml`
   - Database connection failed → Check credentials in `.env`
   - Celery not processing → Check Redis is running

---

## 🎓 Learning the New System

After migration, familiarize yourself with:

1. **New project structure** (see IMPLEMENTATION_SUMMARY.md)
2. **API documentation** at http://localhost:8001/docs
3. **Custom strategy creation** (see README_NEW.md)
4. **Performance metrics** (see backtesting/metrics.py)
5. **Monitoring tools** (Flower, logs, health checks)

---

**Migration Support**: Refer to README_NEW.md and IMPLEMENTATION_SUMMARY.md for detailed documentation.
