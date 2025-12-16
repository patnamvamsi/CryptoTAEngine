# CryptoTA Trading Engine v2.0

Advanced backtesting and trading engine for cryptocurrencies with distributed processing, comprehensive metrics, and production-ready architecture.

## 🚀 New Features (v2.0)

### Architecture Improvements
- ✅ **Modular structure** with separation of concerns
- ✅ **Dependency injection** using FastAPI's DI system
- ✅ **Comprehensive error handling** with custom exceptions
- ✅ **Structured logging** with JSON output for production
- ✅ **Configuration management** using Pydantic Settings
- ✅ **Type safety** throughout the codebase

### Database Layer
- ✅ **PostgreSQL** for storing backtest results and metadata
- ✅ **TimescaleDB** for efficient time series data storage
- ✅ **SQLAlchemy ORM** with proper models and relationships
- ✅ **Automatic schema management**

### Performance & Scalability
- ✅ **Distributed backtesting** using Celery + Redis
- ✅ **Parallel processing** for parameter optimization
- ✅ **Redis caching** for backtest results
- ✅ **Connection pooling** for database efficiency
- ✅ **Background task processing**

### Backtesting Enhancements
- ✅ **Comprehensive metrics** (30+ performance indicators)
  - Returns: Total, Annual, CAGR
  - Risk: Volatility, Max Drawdown, VaR, CVaR
  - Risk-Adjusted: Sharpe, Sortino, Calmar
  - Trading: Win rate, Profit factor, Avg win/loss
  - Benchmark: Alpha, Beta, Information Ratio
- ✅ **Parameter optimization** with grid search
- ✅ **Walk-forward analysis** for robust validation
- ✅ **Base strategy classes** for easy extension
- ✅ **Multiple strategy variants** (RSI, RSI+MA, RSI Divergence)

### API Improvements
- ✅ **RESTful design** with proper HTTP methods
- ✅ **Async job submission** with status tracking
- ✅ **Rate limiting** to prevent abuse
- ✅ **Health checks** for all services
- ✅ **API documentation** with OpenAPI/Swagger
- ✅ **CORS support** for frontend integration

### Data Management
- ✅ **Binance integration** with async support
- ✅ **Multiple symbol fetching** in parallel
- ✅ **Data caching** to reduce API calls
- ✅ **Historical data storage** in TimescaleDB
- ✅ **Continuous aggregates** for downsampling

### DevOps & Deployment
- ✅ **Docker Compose** for multi-service setup
- ✅ **Environment-based configuration**
- ✅ **Service health monitoring**
- ✅ **Celery Flower** for task monitoring
- ✅ **Production-ready logging**

## 📁 Project Structure

```
CryptoTAEngine/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── backtest.py      # Backtest endpoints
│   │   │   ├── health.py        # Health check endpoints
│   │   │   └── data.py          # Data fetching endpoints
│   │   └── dependencies.py      # DI dependencies
│   ├── core/
│   │   ├── config.py            # Settings & configuration
│   │   ├── models.py            # Pydantic models
│   │   └── exceptions.py        # Custom exceptions
│   ├── strategies/
│   │   ├── base.py              # Base strategy classes
│   │   └── rsi_strategy.py      # RSI strategies
│   ├── backtesting/
│   │   ├── engine.py            # Backtesting engine
│   │   ├── metrics.py           # Performance metrics
│   │   └── tasks.py             # Celery tasks
│   ├── data/
│   │   ├── providers/
│   │   │   └── binance_provider.py  # Binance API client
│   │   ├── storage/
│   │   │   ├── database.py      # PostgreSQL models
│   │   │   └── timeseries.py    # TimescaleDB integration
│   │   └── preprocessing/
│   ├── execution/
│   │   └── broker_adapters/
│   ├── utils/
│   │   ├── cache.py             # Redis caching
│   │   └── logging_config.py    # Logging setup
│   ├── main.py                  # FastAPI app
│   ├── celery_app.py            # Celery configuration
│   └── grid_bot.py              # Grid trading bot
├── docker-compose.yml           # Multi-service setup
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies
├── .env.template                # Environment template
└── README_NEW.md                # This file
```

## 🛠️ Installation & Setup

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**
```bash
cd /Users/vamsi/Projects/CryptoTAEngine
```

2. **Create environment file**
```bash
cp .env.template .env
# Edit .env and add your Binance API credentials
```

3. **Start all services**
```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- TimescaleDB (port 5433)
- Redis (port 6379)
- FastAPI app (port 8001)
- Celery worker
- Celery beat (scheduler)
- Flower (monitoring at port 5555)

4. **Access the API**
- API: http://localhost:8001
- Docs: http://localhost:8001/docs
- Flower: http://localhost:5555

### Option 2: Local Development

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Set up databases**
```bash
# Start PostgreSQL and Redis (using Docker or local install)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -p 5433:5432 -e POSTGRES_PASSWORD=postgres timescale/timescaledb:latest-pg15
```

3. **Configure environment**
```bash
cp .env.template .env
# Edit .env with your settings
```

4. **Run migrations**
```bash
cd app
python -c "from data.storage.database import db_manager; db_manager.initialize(); db_manager.create_tables()"
```

5. **Start the API**
```bash
uvicorn main:app --reload --port 8001
```

6. **Start Celery worker** (in separate terminal)
```bash
celery -A celery_app worker --loglevel=info
```

## 📊 API Usage Examples

### 1. Run a Backtest

```bash
curl -X POST "http://localhost:8001/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

Response:
```json
{
  "job_id": "abc123",
  "status": "submitted",
  "message": "Backtest submitted successfully"
}
```

### 2. Check Backtest Status

```bash
curl "http://localhost:8001/backtest/abc123/status"
```

### 3. Get Backtest Results

```bash
curl "http://localhost:8001/backtest/abc123/results"
```

Response includes:
```json
{
  "job_id": "abc123",
  "strategy": "rsi",
  "symbol": "BTCUSDT",
  "metrics": {
    "total_return": 25.5,
    "sharpe_ratio": 1.45,
    "max_drawdown": -15.2,
    "win_rate": 58.3,
    "total_trades": 120,
    ...
  },
  "trades": [...],
  "equity_curve": [...],
  "plot_html": "..."
}
```

### 4. Optimize Strategy Parameters

```bash
curl -X POST "http://localhost:8001/backtest/optimize" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### 5. Fetch Historical Data

```bash
curl -X POST "http://localhost:8001/data/fetch" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "timeframe": "15m",
    "start_date": "2023-01-01T00:00:00",
    "end_date": "2023-01-31T23:59:59"
  }'
```

### 6. Health Check

```bash
curl "http://localhost:8001/health"
```

## 🎯 Creating Custom Strategies

### Basic Strategy

```python
from strategies.base import LongOnlyStrategy
from typing import Dict
import backtrader as bt

class MyStrategy(LongOnlyStrategy):
    params = (
        ('period', 20),
        ('printlog', False),
    )

    def setup_indicators(self):
        """Initialize your indicators."""
        self.sma = bt.indicators.SMA(self.data.close, period=self.params.period)

    def generate_signals(self) -> Dict[str, bool]:
        """Generate buy/sell signals."""
        signals = {'buy': False, 'sell': False}

        # Buy when price crosses above SMA
        if self.data.close[0] > self.sma[0] and self.data.close[-1] <= self.sma[-1]:
            signals['buy'] = True

        # Sell when price crosses below SMA
        if self.data.close[0] < self.sma[0] and self.data.close[-1] >= self.sma[-1]:
            signals['sell'] = True

        return signals
```

### Advanced Strategy with Multiple Indicators

```python
from strategies.base import LongOnlyStrategy
from typing import Dict
import backtrader as bt

class AdvancedStrategy(LongOnlyStrategy):
    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
        ('rsi_period', 14),
    )

    def setup_indicators(self):
        """Initialize multiple indicators."""
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.params.fast_period,
            period_me2=self.params.slow_period,
            period_signal=self.params.signal_period
        )
        self.rsi = bt.indicators.RSI(period=self.params.rsi_period)

    def generate_signals(self) -> Dict[str, bool]:
        """Generate signals using multiple conditions."""
        signals = {'buy': False, 'sell': False}

        # Buy: MACD crosses above signal AND RSI < 70
        if (self.macd.macd[0] > self.macd.signal[0] and
            self.macd.macd[-1] <= self.macd.signal[-1] and
            self.rsi[0] < 70):
            signals['buy'] = True

        # Sell: MACD crosses below signal OR RSI > 80
        if (self.macd.macd[0] < self.macd.signal[0] and
            self.macd.macd[-1] >= self.macd.signal[-1]) or self.rsi[0] > 80:
            signals['sell'] = True

        return signals
```

## 📈 Performance Metrics Explained

### Returns
- **Total Return**: Overall percentage gain/loss
- **Annual Return**: Annualized return percentage
- **CAGR**: Compound Annual Growth Rate

### Risk
- **Volatility**: Standard deviation of returns (annualized)
- **Max Drawdown**: Largest peak-to-trough decline
- **VaR (95%)**: Value at Risk at 95% confidence
- **CVaR (95%)**: Conditional VaR (expected loss beyond VaR)

### Risk-Adjusted
- **Sharpe Ratio**: Excess return per unit of risk
- **Sortino Ratio**: Like Sharpe but uses downside deviation
- **Calmar Ratio**: CAGR divided by max drawdown

### Trading
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / Gross loss
- **Avg Win/Loss**: Average profit/loss per trade

## 🔧 Configuration

All configuration is managed through environment variables (see `.env.template`).

Key configurations:
- **Database URLs**: PostgreSQL, TimescaleDB
- **Redis**: Caching and Celery broker
- **Binance API**: Trading pair data source
- **Backtesting**: Initial capital, commission rates
- **Performance**: Worker count, parallel backtests

## 🐛 Debugging & Monitoring

### Logs
Structured JSON logs are written to stdout:
```bash
docker-compose logs -f api
docker-compose logs -f celery_worker
```

### Celery Flower
Monitor Celery tasks at http://localhost:5555

### Database
Connect to PostgreSQL:
```bash
docker exec -it cryptota_postgres psql -U postgres -d trading_engine
```

Query backtest results:
```sql
SELECT id, strategy, symbol, total_return, sharpe_ratio, status
FROM backtest_runs
ORDER BY created_at DESC
LIMIT 10;
```

## 🚀 Large-Scale Backtesting Recommendations

For backtesting at scale (millions of data points, hundreds of strategies):

1. **Use Celery** for distributing backtests across multiple workers
2. **Consider vectorbt** for 1000x faster backtests (uncomment in requirements.txt)
3. **Implement walk-forward analysis** for robust validation
4. **Use TimescaleDB continuous aggregates** for data downsampling
5. **Cache aggressively** - similar backtests return instantly from Redis
6. **Partition data** by symbol and date range
7. **Run optimization in parallel** using grid search
8. **Monitor with Flower** to track task progress

## 📝 Critical Fixes Applied

1. ✅ **Grid bot bug** (line 97) - Fixed incorrect order type
2. ✅ **Hardcoded paths** - Now use environment variables
3. ✅ **Missing metrics** - Added 30+ performance indicators
4. ✅ **No error handling** - Comprehensive exception handling
5. ✅ **Security** - API keys from environment, not code
6. ✅ **Scalability** - Distributed processing with Celery

## 🔮 Future Enhancements

- [ ] WebSocket support for real-time data
- [ ] Machine learning integration for strategy optimization
- [ ] Multi-asset portfolio backtesting
- [ ] Advanced order types (stop-loss, take-profit, trailing stops)
- [ ] Frontend dashboard for visualization
- [ ] Alert system for live trading signals
- [ ] Integration with additional exchanges
- [ ] Sentiment analysis from social media

## 📄 License

See LICENSE file.

## 🤝 Contributing

This is a microservice within a larger trading platform. For contributions, ensure:
- All tests pass
- Code follows PEP 8
- Type hints are used
- Documentation is updated
