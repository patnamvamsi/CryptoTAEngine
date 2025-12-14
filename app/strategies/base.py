"""
Abstract base class for all trading strategies.
"""
from abc import ABC, abstractmethod
import backtrader as bt
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(bt.Strategy, ABC):
    """
    Abstract base class for trading strategies.

    All custom strategies should inherit from this class and implement:
    - setup_indicators(): Initialize technical indicators
    - generate_signals(): Generate buy/sell signals
    """

    # Default parameters (can be overridden by subclasses)
    params = (
        ('printlog', False),
        ('position_size', 1.0),
    )

    def __init__(self):
        """Initialize strategy."""
        super().__init__()

        # Track orders and trades
        self.order = None
        self.trades_list = []
        self.portfolio_values = []
        self.dates = []

        # Setup strategy-specific indicators
        self.setup_indicators()

        logger.info(f"Initialized {self.__class__.__name__}")

    @abstractmethod
    def setup_indicators(self):
        """
        Initialize strategy-specific indicators.

        Override this method to create your indicators.
        Example:
            self.sma = bt.indicators.SMA(self.data.close, period=20)
            self.rsi = bt.indicators.RSI(period=14)
        """
        pass

    @abstractmethod
    def generate_signals(self) -> Dict[str, bool]:
        """
        Generate trading signals.

        Override this method to implement your trading logic.

        Returns:
            Dict with 'buy' and 'sell' boolean signals
            Example: {'buy': True, 'sell': False}
        """
        pass

    def next(self):
        """
        Called for each bar in the data.
        This is the main execution loop.
        """
        # Record portfolio value and date
        self.portfolio_values.append(self.broker.getvalue())
        self.dates.append(self.data.datetime.date(0))

        # Don't trade if an order is pending
        if self.order:
            return

        # Generate signals
        signals = self.generate_signals()

        # Execute trades based on signals
        if signals.get('buy', False) and not self.position:
            self.execute_buy()

        elif signals.get('sell', False) and self.position:
            self.execute_sell()

    def execute_buy(self):
        """Execute a buy order."""
        size = self.calculate_position_size()
        if size > 0:
            self.order = self.buy(size=size)
            self.log(f'BUY ORDER, Price: {self.data.close[0]:.2f}, Size: {size}')

    def execute_sell(self):
        """Execute a sell order (close position)."""
        self.order = self.close()
        self.log(f'SELL ORDER, Price: {self.data.close[0]:.2f}')

    def calculate_position_size(self) -> float:
        """
        Calculate position size based on available capital.

        Override this for custom position sizing (e.g., Kelly Criterion).

        Returns:
            Position size (number of units to buy)
        """
        return self.params.position_size

    def notify_order(self, order):
        """Called when order status changes."""
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted - nothing to do
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
                )
            elif order.issell():
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
                )

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected: {order.status}')

        # Reset order
        self.order = None

    def notify_trade(self, trade):
        """Called when a trade is closed."""
        if not trade.isclosed:
            return

        # Record trade details
        trade_record = {
            'date': self.data.datetime.date(0),
            'profit': trade.pnl,
            'profit_net': trade.pnlcomm,
            'commission': trade.commission
        }
        self.trades_list.append(trade_record)

        self.log(
            f'TRADE CLOSED, Gross P&L: {trade.pnl:.2f}, Net P&L: {trade.pnlcomm:.2f}'
        )

    def stop(self):
        """Called when backtesting is complete."""
        final_value = self.broker.getvalue()
        initial_value = self.portfolio_values[0] if self.portfolio_values else 0

        self.log(
            f'Strategy Complete: {self.__class__.__name__}, '
            f'Initial Value: {initial_value:.2f}, Final Value: {final_value:.2f}, '
            f'Total Trades: {len(self.trades_list)}'
        )

    def log(self, txt, dt=None):
        """Logging function for the strategy."""
        if self.params.printlog:
            dt = dt or self.data.datetime.date(0)
            print(f'{dt.isoformat()} {txt}')

    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Get list of all trades.

        Returns:
            List of trade dictionaries
        """
        return self.trades_list

    def get_portfolio_values(self) -> List[float]:
        """
        Get time series of portfolio values.

        Returns:
            List of portfolio values
        """
        return self.portfolio_values

    def get_dates(self) -> List[datetime]:
        """
        Get dates corresponding to portfolio values.

        Returns:
            List of dates
        """
        return self.dates


class LongOnlyStrategy(BaseStrategy, ABC):
    """
    Base class for long-only strategies (no short selling).
    """

    def execute_sell(self):
        """Only close existing positions, don't short."""
        if self.position:
            super().execute_sell()


class LongShortStrategy(BaseStrategy, ABC):
    """
    Base class for long/short strategies.
    """

    def execute_sell(self):
        """Can sell to close long or open short."""
        # Close long if we have one
        if self.position.size > 0:
            self.close()

        # Open short position
        else:
            size = self.calculate_position_size()
            if size > 0:
                self.order = self.sell(size=size)
                self.log(f'SHORT ORDER, Price: {self.data.close[0]:.2f}, Size: {size}')
