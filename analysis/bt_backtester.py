# -*- coding: utf-8 -*-
import sys
import os
import datetime
import backtrader as bt
import pandas as pd
import pandas_ta as ta
import numpy as np

# 確保路徑正確
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from analysis.improved_pattern_analyzer import ImprovedPatternAnalyzer
from data.data_fetcher import get_data_fetcher

class PandasDataPlus(bt.feeds.PandasData):
    """擴展 Backtrader 的數據類，以包含自定義指標列"""
    lines = ('adx', 'atr',)
    params = (
        ('adx', -1),
        ('atr', -1),
    )

class PatternStrategy(bt.Strategy):
    params = (
        ('window', 10),
        ('tp_ratio', 2.0),       # 提高盈虧比預期
        ('sl_atr_mult', 2.0),    # 止損設為 2 倍 ATR
        ('risk_per_trade', 0.9), 
        ('adx_threshold', 20),   # ADX 低於此值視為震盪，不交易
        ('debug', True)
    )

    def __init__(self):
        self.analyzer = ImprovedPatternAnalyzer(min_points=3, min_size_threshold=0.005)
        self.order = None
        self.trade_list = []

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'{dt.isoformat()} {txt}')

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}')
            elif order.issell():
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}')
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # self.log(f'Order Status: {order.getstatusname()}')
            pass
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f'TRADE CLOSED, NET PNL: {trade.pnlcomm:.2f}')
        self.trade_list.append({'pnl': trade.pnlcomm})

    def next(self):
        if self.order or self.position:
            return

        # 1. 趨勢強度過濾 (ADX)
        if self.data.adx[0] < self.params.adx_threshold:
            return

        # 2. 形態偵測
        lookback = 100
        if len(self) < lookback: return
        
        df = pd.DataFrame({
            'Open': np.array(self.data.open.get(ago=0, size=lookback)),
            'High': np.array(self.data.high.get(ago=0, size=lookback)),
            'Low': np.array(self.data.low.get(ago=0, size=lookback)),
            'Close': np.array(self.data.close.get(ago=0, size=lookback))
        })
        
        pattern = self.analyzer.find_best_pattern(df, window=self.params.window, require_recent=True)
        if not pattern or pattern.end_idx < lookback - 15:
            return

        # 3. 計算下一根預測位與 ATR 止損
        next_idx = lookback # 下一根
        pred_high = pattern.trendline_high[0] * next_idx + pattern.trendline_high[1]
        pred_low = pattern.trendline_low[0] * next_idx + pattern.trendline_low[1]
        
        current_atr = self.data.atr[0]
        cash = self.broker.get_cash()
        size = (cash * self.params.risk_per_trade) / self.data.close[0]

        # 判斷突破方向掛單
        dist_to_high = abs(self.data.close[0] - pred_high)
        dist_to_low = abs(self.data.close[0] - pred_low)

        if dist_to_high < dist_to_low:
            # 做多掛單
            trigger_price = pred_high * 1.001
            # 使用 ATR 設定止損，讓止損更具彈性
            sl_price = trigger_price - (current_atr * self.params.sl_atr_mult)
            # 盈虧比 1:2
            tp_price = trigger_price + (current_atr * self.params.sl_atr_mult * self.params.tp_ratio)
            
            if trigger_price > self.data.close[0]: # 確保是向上突破
                self.buy_bracket(price=trigger_price, limitprice=tp_price, stopprice=sl_price, 
                                 exectype=bt.Order.Stop, size=size)
                if self.params.debug:
                    self.log(f'Set LONG Breakout @ {trigger_price:.2f} (ADX: {self.data.adx[0]:.1f})')
        else:
            # 做空掛單
            trigger_price = pred_low * 0.999
            sl_price = trigger_price + (current_atr * self.params.sl_atr_mult)
            tp_price = trigger_price - (current_atr * self.params.sl_atr_mult * self.params.tp_ratio)
            
            if trigger_price < self.data.close[0]: # 確保是向下跌破
                self.sell_bracket(price=trigger_price, limitprice=tp_price, stopprice=sl_price, 
                                  exectype=bt.Order.Stop, size=size)
                if self.params.debug:
                    self.log(f'Set SHORT Breakout @ {trigger_price:.2f} (ADX: {self.data.adx[0]:.1f})')

def run_backtrader_backtest(symbol, interval="1h", limit=1000):
    print(f"\n========== Backtrader 升級版回測 (ADX+ATR): {symbol} ==========")
    cerebro = bt.Cerebro()
    cerebro.addstrategy(PatternStrategy)
    
    fetcher = get_data_fetcher("okx")
    df = fetcher.get_historical_klines(symbol, interval, limit)
    if df is None or df.empty: return

    # 使用 pandas_ta 計算指標
    df['adx'] = ta.adx(df['High'], df['Low'], df['Close'])['ADX_14']
    df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df.fillna(0, inplace=True)
    
    df['datetime'] = pd.to_datetime(df['Open_time'])
    df.set_index('datetime', inplace=True)
    
    data = PandasDataPlus(
        dataname=df, 
        open='Open', high='High', low='Low', close='Close', volume='Volume',
        adx='adx', atr='atr'
    )
    cerebro.adddata(data)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)
    
    print(f'初始資金: {cerebro.broker.getvalue():.2f}')
    cerebro.run()
    print(f'最終資金: {cerebro.broker.getvalue():.2f}')

if __name__ == "__main__":
    for sym in ["BTC-USDT", "ETH-USDT", "SOL-USDT"]:
        run_backtrader_backtest(sym, "1h", 1000)