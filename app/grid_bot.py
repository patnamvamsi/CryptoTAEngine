from binance.client import Client
from config import config
from binance import ThreadedWebsocketManager
from binance.enums import *
import time, sys

SYMBOL = "XRPAUD"
POSITION_SIZE = 10

# grid bot settings
NUM_BUY_GRID_LINES = 3
NUM_SELL_GRID_LINES = 3
GRID_SIZE_PRCNT = 0.002

CHECK_ORDERS_FREQUENCY = 10
ALIVE_ORDER_STATUS = ['NEW','PARTIALLY_FILLED']
FILLED_ORDER_STATUS = 'FILLED'

client = Client(config.API_KEY, config.API_SECRET)

def grid_bot():

    buy_orders = []
    sell_orders = []



    for i in range(NUM_BUY_GRID_LINES):
        bid = float(get_l1_orderbook('bid'))
        price =  round(bid - (bid * GRID_SIZE_PRCNT *(i+1)),4)
        print("submitting market limit buy order at {}".format(price))
        order = client.create_test_order(
                symbol=SYMBOL,
                side=SIDE_BUY,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=POSITION_SIZE,
                price=price)
        order = client.order_limit_buy(symbol=SYMBOL, quantity=POSITION_SIZE, price=price)
        buy_orders.append(order)

    for j in range(NUM_SELL_GRID_LINES):

        ask = float(get_l1_orderbook('ask')) #iki may be use bid
        price = round(ask + (ask * GRID_SIZE_PRCNT * (j+1)), 4)
        print("submitting market limit sell order at {}".format(price))
        order = client.create_test_order(
                symbol=SYMBOL,
                side=SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=POSITION_SIZE,
                price=price)
        order = client.order_limit_sell(symbol=SYMBOL, quantity=POSITION_SIZE, price=price)
        sell_orders.append(order)


    while True:
        closed_order_ids = []

        for buy_order in buy_orders:
            print("checking buy order {}".format(buy_order['orderId']))
            try:
                order = client.get_order(symbol=SYMBOL, orderId=buy_order['orderId'])
            except Exception as e:
                print("request failed, retrying")
                continue

            #order_info = order['info']

            if order['status']  in FILLED_ORDER_STATUS:
                closed_order_ids.append(order['orderId'])
                print("buy order executed at {}".format(order['price']))
                new_sell_price = round(float(order['price']) + (float(order['price']) * GRID_SIZE_PRCNT), 4)
                print("creating new limit sell order at {}".format(new_sell_price))
                new_sell_order = client.order_limit_sell(symbol=SYMBOL, quantity=POSITION_SIZE, price=new_sell_price)
                sell_orders.append(new_sell_order)

            time.sleep(CHECK_ORDERS_FREQUENCY)

        for sell_order in sell_orders:
            print("checking sell order {}".format(sell_order['orderId']))
            try:
                order = client.get_order(symbol=SYMBOL, orderId=sell_order['orderId'])
            except Exception as e:
                print("request failed, retrying")
                continue

            #order_info = order['info']

            if order['status'] in FILLED_ORDER_STATUS:
                closed_order_ids.append(order['orderId'])
                print("sell order executed at {}".format(order['price']))
                new_buy_price = round(float(order['price']) - (float(order['price']) * GRID_SIZE_PRCNT), 4)
                print("creating new limit buy order at {}".format(new_buy_price))
                print(get_binance_positions())
                new_buy_order = client.order_limit_buy(symbol=SYMBOL, quantity=POSITION_SIZE, price=new_buy_price)
                buy_orders.append(new_buy_order)

            time.sleep(CHECK_ORDERS_FREQUENCY)

        for order_id in closed_order_ids:
            buy_orders = [buy_order for buy_order in buy_orders if buy_order['orderId'] != order_id]
            sell_orders = [sell_order for sell_order in sell_orders if sell_order['orderId'] != order_id]

        if len(sell_orders) == 0:
            sys.exit("stopping bot, nothing left to sell")

def get_l1_orderbook(type):
    order = client.get_order_book(symbol=SYMBOL)

    if type == 'bid':
        print("Latest bid: {}".format(order['bids'][0][0]))
        return order['bids'][0][0]
    else:
        print("Latest ask: {}".format(order['asks'][0][0]))
        return order['asks'][0][0]


def get_binance_positions():
    client = Client(config.API_KEY, config.API_SECRET)
    account = client.get_account()
    balances = []
    balances_all = account['balances']

    for x in balances_all:
        if not (float(x['free']) == 0 and float(x['locked']) == 0):
            x['total'] = float(x['free']) + float(x['locked'])
            balances.append(x)

    return balances


grid_bot()

"""
if ran out of Symbols to sell, buy at best bid at the moment  = position * grid size to be back in the game -- Very risky

restarting the bot should rcover from current position and orfders
not start all over again

"""