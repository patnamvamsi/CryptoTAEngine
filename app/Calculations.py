'''
Putting together all the calculations that might be useful in futuire references
'''
import math
from scipy.stats import norm



'''
Black scholes European call option therotical price calculation:
source: https://www.youtube.com/watch?v=xtjxl7ozuuc&t=5s
Assumptions:

'''
def get_black_scholes_call_price(r,S,K,T,vol):
    d1 = (math.log(S/K) + (r+vol**2/2)*T)/(vol*T**(1/2))
    d2 = d1 - vol*T**(1/2)
    return S*norm.cdf(d1,0,1) - K * math.exp(-r*T)*norm.cdf(d2,0,1)

def test_get_black_scholes_call_price():
    current_price = 100
    interest_rate = 0.04
    strike_price = 100
    time_to_maturity = 30/365
    volatility = 0.25

    print(get_black_scholes_call_price(interest_rate,current_price,strike_price,time_to_maturity,volatility))



if __name__ == '__main__':
    test_get_black_scholes_call_price()
