import datetime
import backtrader as bt
import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Dict, Optional

# Define a custom data feed that supports additional indicators if needed
class PandasData(bt.feeds.PandasData):
    lines = ('rsi', 'macd', 'macdsignal', 'ma_fast', 'ma_slow',)
    params = (
        ('rsi', -1),
        ('macd', -1),
        ('macdsignal', -1),
        ('ma_fast', -1),
        ('ma_slow', -1),
    )

class SimpleSignalStrategy(bt.Strategy):
    """
    A generic strategy to backtest simple technical signals.
    """
    params = (
        ('signal_type', 'RSI'), # RSI, MACD, MA_CROSS
        ('tp_ratio', 1.5),      # Take Profit / Stop Loss ratio
        ('sl_pct', 0.02),       # Stop Loss percentage
    )

    def __init__(self):
        self.order = None
        self.buy_price = None
        self.buy_comm = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            self.buy_price = order.executed.price
            self.buy_comm = order.executed.comm
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def next(self):
        if self.order: # Pending order
            return

        if not self.position: # Not in market
            signal = False
            
            if self.params.signal_type == 'RSI':
                if self.data.rsi[0] < 30 and self.data.rsi[-1] >= 30: # Cross above 30
                    signal = True
            
            elif self.params.signal_type == 'MACD':
                # Golden Cross: MACD crosses above Signal
                if self.data.macd[-1] < self.data.macdsignal[-1] and self.data.macd[0] > self.data.macdsignal[0]:
                    signal = True
            
            elif self.params.signal_type == 'MA_CROSS':
                # Fast crosses above Slow
                if self.data.ma_fast[-1] < self.data.ma_slow[-1] and self.data.ma_fast[0] > self.data.ma_slow[0]:
                    signal = True

            if signal:
                # Buy with Bracket Order (Stop Loss & Take Profit)
                price = self.data.close[0]
                stop_price = price * (1.0 - self.params.sl_pct)
                limit_price = price * (1.0 + (self.params.sl_pct * self.params.tp_ratio))
                
                self.buy_bracket(limitprice=limit_price, stopprice=stop_price)
                
        else:
            # Position is managed by bracket order, but we can add trailing stop logic here if needed
            pass

def run_simple_backtest(
    symbol: str, 
    signal_type: str = "RSI", 
    interval: str = "1h", 
    limit: int = 500
) -> Dict:
    """
    Runs a quick backtest for a specific signal.
    """
    try:
        from data.data_fetcher import get_data_fetcher
        
        # 1. Get Data
        fetcher = get_data_fetcher("okx") # Default to OKX or generic
        df = fetcher.get_historical_klines(symbol, interval, limit)
        
        if df is None or df.empty:
            return {"error": "No data found"}

        # 2. Calculate Indicators using pandas_ta
        # Pre-calculate to pass to Backtrader
        if signal_type == "RSI":
            df['rsi'] = ta.rsi(df['Close'], length=14)
        elif signal_type == "MACD":
            macd = ta.macd(df['Close'])
            df['macd'] = macd['MACD_12_26_9']
            df['macdsignal'] = macd['MACDs_12_26_9']
        elif signal_type == "MA_CROSS":
            df['ma_fast'] = ta.sma(df['Close'], length=7)
            df['ma_slow'] = ta.sma(df['Close'], length=25)

        df = df.fillna(0)
        df['datetime'] = pd.to_datetime(df['Open_time'])
        df.set_index('datetime', inplace=True)

        # 3. Setup Backtrader
        cerebro = bt.Cerebro()
        cerebro.addstrategy(SimpleSignalStrategy, signal_type=signal_type)

        data = PandasData(
            dataname=df,
            open='Open', high='High', low='Low', close='Close', volume='Volume',
            rsi='rsi' if 'rsi' in df else None,
            macd='macd' if 'macd' in df else None,
            macdsignal='macdsignal' if 'macdsignal' in df else None,
            ma_fast='ma_fast' if 'ma_fast' in df else None,
            ma_slow='ma_slow' if 'ma_slow' in df else None,
        )
        
        cerebro.adddata(data)
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)

        # Add Analyzers
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

        # 4. Run
        initial_value = cerebro.broker.getvalue()
        results = cerebro.run()
        final_value = cerebro.broker.getvalue()
        strat = results[0]

        # 5. Extract Metrics
        trade_analysis = strat.analyzers.trades.get_analysis()
        drawdown_analysis = strat.analyzers.drawdown.get_analysis()
        
        total_trades = trade_analysis.get('total', {}).get('total', 0)
        win_trades = trade_analysis.get('won', {}).get('total', 0)
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
        
        pnl = final_value - initial_value
        return_pct = (pnl / initial_value) * 100
        max_drawdown = drawdown_analysis.get('max', {}).get('drawdown', 0)

        return {
            "symbol": symbol,
            "signal_type": signal_type,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "return_pct": return_pct,
            "max_drawdown": max_drawdown,
            "initial_capital": initial_value,
            "final_capital": final_value
        }

    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Test
    print(run_simple_backtest("BTC-USDT", "RSI"))
