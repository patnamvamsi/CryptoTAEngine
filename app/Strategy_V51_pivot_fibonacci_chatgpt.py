import pandas as pd
import sqlite3  # You can replace this with any other database library
from datetime import datetime
pd.options.mode.chained_assignment = None  # default='warn'

# Function to calculate SMA
def calculate_sma(data, period):
    return data['Close'].rolling(window=period).mean()

# Function to calculate Pivot Points and Fibonacci levels
def calculate_pivot_fibonacci(data):
    pivot_data = pd.DataFrame()
    pivot_data['P'] = (data['High'] + data['Low'] + data['Close']) / 3
    pivot_data['S3'] = pivot_data['P'] - 1.618 * (data['High'] - data['Low'])  # Fibonacci S3
    return pivot_data

# Backtesting strategy
def backtest_strategy(data):
    data['SMA_200'] = calculate_sma(data, 200)
    pivot_data = calculate_pivot_fibonacci(data)
    data['P'] = pivot_data['P']
    data['S3'] = pivot_data['S3']

    position = False
    buy_price = 0
    trades = []

    for index, row in data.iterrows():
        if not position and row['SMA_200'] < row['S3']:  # Buy signal
            position = True
            buy_price = row['Close']
            trades.append({'Date': row.name, 'Action': 'BUY', 'Price': buy_price})

        elif position and row['Close'] > row['P']:  # Sell signal
            position = False
            sell_price = row['Close']
            trades.append({'Date': row.name, 'Action': 'SELL', 'Price': sell_price})

    return trades

# Connect to database and fetch OHLC data
def fetch_ohlc_data(database_path, table_name):
    connection = sqlite3.connect(database_path)
    query = f"SELECT Date, Open, High, Low, Close FROM {table_name}"
    data = pd.read_sql(query, connection, parse_dates=['Date'], index_col='Date')
    connection.close()
    return data

def fetch_ohlc_data_from_file():
    data = pd.read_csv("data//vivek_v51_stocks.csv", parse_dates=['date1'])
    data.rename(columns={'open_price': 'Open','close_price': 'Close',
                         'high_price': 'High', 'low_price': 'Low', 'date1': 'Date'
                         }, inplace=True)
    data = data.set_index('Date')

    return data

# Main script
if __name__ == "__main__":

    # Replace with your database path and table name
    """
    database_path = 'ohlc_data.db'
    table_name = 'stocks'
    ohlc_data = fetch_ohlc_data(database_path, table_name)
    """
    ohlc_data = fetch_ohlc_data_from_file()
    ohlc_data.sort_index(inplace=True)

    stock_list = ohlc_data['symbol'].unique()
    for stock in stock_list:
        stock_ohlc_data = ohlc_data[ohlc_data['symbol'] == stock]
        print (f'Processing: {stock}')
        trades = backtest_strategy(stock_ohlc_data)

        # Output trades and calculate total profit/loss
        profit = 0
        for i in range(1, len(trades), 2):  # Iterate over sell trades
            buy = trades[i - 1]
            sell = trades[i]
            profit += sell['Price'] - buy['Price']
            print(f"Trade: {buy['Date']} {buy['Action']} at {buy['Price']}, {sell['Date']} {sell['Action']} at {sell['Price']}")

        print(f"Total Profit/Loss: {profit}")
        exit(0)
