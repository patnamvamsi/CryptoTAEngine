"""
RSI (Relative Strength Index) trading strategy.
"""
import backtrader as bt
from typing import Dict
from strategies.base import LongOnlyStrategy


class RSIStrategy(LongOnlyStrategy):
    """
    RSI-based trading strategy.

    Strategy Logic:
    - BUY when RSI < oversold threshold (default 30)
    - SELL when RSI > overbought threshold (default 70)
    """

    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
        ('position_size', 1.0),
        ('printlog', False),
    )

    def setup_indicators(self):
        """Initialize RSI indicator."""
        self.rsi = bt.talib.RSI(self.data, period=self.params.rsi_period)

    def generate_signals(self) -> Dict[str, bool]:
        """
        Generate buy/sell signals based on RSI.

        Returns:
            Dict with 'buy' and 'sell' signals
        """
        signals = {
            'buy': False,
            'sell': False
        }

        # Check if we have enough data
        if len(self.data) < self.params.rsi_period:
            return signals

        # Buy signal: RSI crosses below oversold
        if self.rsi[0] < self.params.oversold:
            signals['buy'] = True

        # Sell signal: RSI crosses above overbought
        if self.rsi[0] > self.params.overbought:
            signals['sell'] = True

        return signals


class RSIMACrossStrategy(LongOnlyStrategy):
    """
    Enhanced RSI strategy with Moving Average confirmation.

    Strategy Logic:
    - BUY when RSI < oversold AND price > MA (uptrend)
    - SELL when RSI > overbought OR price < MA (downtrend)
    """

    params = (
        ('rsi_period', 14),
        ('oversold', 30),
        ('overbought', 70),
        ('ma_period', 50),
        ('position_size', 1.0),
        ('printlog', False),
    )

    def setup_indicators(self):
        """Initialize RSI and MA indicators."""
        self.rsi = bt.talib.RSI(self.data, period=self.params.rsi_period)
        self.ma = bt.indicators.SimpleMovingAverage(
            self.data.close,
            period=self.params.ma_period
        )

    def generate_signals(self) -> Dict[str, bool]:
        """Generate signals with MA confirmation."""
        signals = {
            'buy': False,
            'sell': False
        }

        # Need enough data
        if len(self.data) < max(self.params.rsi_period, self.params.ma_period):
            return signals

        # Buy: RSI oversold AND price above MA (uptrend)
        if self.rsi[0] < self.params.oversold and self.data.close[0] > self.ma[0]:
            signals['buy'] = True

        # Sell: RSI overbought OR price below MA
        if self.rsi[0] > self.params.overbought or self.data.close[0] < self.ma[0]:
            signals['sell'] = True

        return signals


class RSIDivergenceStrategy(LongOnlyStrategy):
    """
    RSI divergence strategy (advanced).

    Looks for divergence between price and RSI:
    - Bullish divergence: Price makes lower low, RSI makes higher low → BUY
    - Bearish divergence: Price makes higher high, RSI makes lower high → SELL
    """

    params = (
        ('rsi_period', 14),
        ('lookback', 5),
        ('position_size', 1.0),
        ('printlog', False),
    )

    def setup_indicators(self):
        """Initialize RSI indicator."""
        self.rsi = bt.talib.RSI(self.data, period=self.params.rsi_period)

    def generate_signals(self) -> Dict[str, bool]:
        """Generate signals based on RSI divergence."""
        signals = {
            'buy': False,
            'sell': False
        }

        # Need enough data
        if len(self.data) < self.params.rsi_period + self.params.lookback:
            return signals

        # Bullish divergence
        if self._detect_bullish_divergence():
            signals['buy'] = True

        # Bearish divergence
        if self._detect_bearish_divergence():
            signals['sell'] = True

        return signals

    def _detect_bullish_divergence(self) -> bool:
        """Detect bullish divergence (price lower low, RSI higher low)."""
        lookback = self.params.lookback

        # Price makes lower low
        current_price = self.data.close[0]
        past_price = self.data.close[-lookback]
        price_lower_low = current_price < past_price

        # RSI makes higher low
        current_rsi = self.rsi[0]
        past_rsi = self.rsi[-lookback]
        rsi_higher_low = current_rsi > past_rsi

        return price_lower_low and rsi_higher_low

    def _detect_bearish_divergence(self) -> bool:
        """Detect bearish divergence (price higher high, RSI lower high)."""
        lookback = self.params.lookback

        # Price makes higher high
        current_price = self.data.close[0]
        past_price = self.data.close[-lookback]
        price_higher_high = current_price > past_price

        # RSI makes lower high
        current_rsi = self.rsi[0]
        past_rsi = self.rsi[-lookback]
        rsi_lower_high = current_rsi < past_rsi

        return price_higher_high and rsi_lower_high
