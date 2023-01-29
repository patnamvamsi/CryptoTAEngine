import backtrader as bt
import datetime
import plotly
from backtrader_plotting import Bokeh

class cryptoCerbro(bt.Cerebro):
    def plot(self, plotter=None, numfigs=1, iplot=True, start=None, end=None,
             width=16, height=9, dpi=300, tight=True, use=None,
             **kwargs):
        if self._exactbars > 0:
            return

        if not plotter:
            from backtrader import plot
            if self.p.oldsync:
                plotter = plot.Plot_OldSync(**kwargs)
            else:
                plotter = plot.Plot(**kwargs)

        figs = []
        for stratlist in self.runstrats:
            for si, strat in enumerate(stratlist):
                rfig = plotter.plot(strat, figid=si * 100,
                                    numfigs=numfigs, iplot=iplot,
                                    start=start, end=end, use=use)
                # pfillers=pfillers2)

                figs.append(rfig)

            #plotter.show()

        return figs


class RSIStrategy(bt.Strategy):
    def __init__(self):
        self.rsi = bt.talib.RSI(self.data, period=14)

    def next(self):
        if self.rsi < 30 and not self.position:
            self.buy(size=1)

        if self.rsi > 70 and self.position:
            self.close()


def get_backtest_results():
    cerebro = bt.Cerebro()
    cerebro = cryptoCerbro()
    fromdate = datetime.datetime.strptime('2020-07-01', '%Y-%m-%d')
    todate = datetime.datetime.strptime('2020-07-12', '%Y-%m-%d')
    data = bt.feeds.GenericCSVData(dataname='/home/vamsi/Dev/Projects/CryptoTrading/data/2020_15minutes.csv', dtformat=2, compression=15,
                                   timeframe=bt.TimeFrame.Minutes, fromdate=fromdate, todate=todate)

    cerebro.adddata(data)
    cerebro.addstrategy(RSIStrategy)
    result = cerebro.run()
    # explore https://pypi.org/project/backtrader-plotting/ when you get a chance to beautify graphs
    # https://verybadsoldier.github.io/backtrader_plotting/demos/blackly_tabs.html
    # https://verybadsoldier.github.io/backtrader_plotting/demos/tradimo_single.html
    #div = cerebro.plot(tight=True,width=32, height=18, dpi=800)[0][0]
    #b = Bokeh(style='bar', plot_mode='single',output_mode='memory')
    #div = cerebro.plot(b)[0][0]
    div = cerebro.plot()[0][0]

    #div = processPlots(b,width=32, height=18, dpi=800)[0][0]
    return plotly.offline.plot_mpl(div,output_type='div')


def processPlots(self,  numfigs=1, iplot=True, start=None, end=None,
         width=16, height=9, dpi=300, tight=True, use=None, **kwargs):

    # if self._exactbars > 0:
    #     return

    from backtrader import plot
    if self.p.oldsync:
        plotter = plot.Plot_OldSync(**kwargs)
    else:
        plotter = plot.Plot(**kwargs)

    figs = []
    for stratlist in self.runstrats:
        for si, strat in enumerate(stratlist):
            rfig = plotter.plot(strat, figid=si * 100,
                                numfigs=numfigs, iplot=iplot,
                                start=start, end=end, use=use)
            figs.append(rfig)

        # this blocks code execution
        # plotter.show()
    return figs


