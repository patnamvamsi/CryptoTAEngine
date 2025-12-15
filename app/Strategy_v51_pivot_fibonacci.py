from app import config
import csv
import pandas as pd
from backtesting import Backtest, Strategy
import talib
from app.db.timescaledb import timescaledb_connect as c

session_pool = c.get_session_pool()
session = session_pool()


def get_candlesticks(session, ticker_symbol, interval):
    return 0


def calculate_sma(ohlc_df, lookback):
    return 0


def calculate_fibnocci_pivot(ohlc_df, ):
    return 0




class SmaFibonacciPivot(Strategy):

    def init(self, context):
        pass

    def next(self):
        pass
