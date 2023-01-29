from fastapi import FastAPI
import RSI_strategy

app = FastAPI()

@app.get("/")
def read_root():
    return ("First API call success")

@app.get("/backtest")
async def backtest(strategy: str):
    return ("big backtest load")

@app.get("/RSIbacktest")
def RSIbacktest():
    return RSI_strategy.get_backtest_results()