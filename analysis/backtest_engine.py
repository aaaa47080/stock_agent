import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Dict, List, Optional

class BacktestEngine:
    """
    輕量化向量回測引擎
    用於快速驗證常見技術策略在當前K線數據上的歷史表現
    """
    
    @staticmethod
    def calculate_performance(signals: pd.Series, close_prices: pd.Series, strategy_name: str) -> Dict:
        """
        計算策略表現
        signals: 1 (Buy), -1 (Sell), 0 (Hold)
        """
        # 模擬持倉: 1為持有, 0為空手 (這裡簡化為只做多回測，或者多空都做)
        # 為了簡化計算，我們假設信號出現的下一根K線開盤價進場
        
        # 將信號位移一格，模擬"收盤確認信號，下根開盤操作"
        # 這裡我們做簡單的信號回測：
        # Buy Signal -> 持有直到 Sell Signal
        
        position = 0
        entry_price = 0
        trades = []
        
        # 轉換為 numpy 加速遍歷
        sig_arr = signals.values
        price_arr = close_prices.values
        dates = close_prices.index
        
        for i in range(len(sig_arr) - 1): # 最後一根無法在下一根結算
            current_signal = sig_arr[i]
            current_price = price_arr[i]
            
            if position == 0:
                if current_signal == 1: # Open Long
                    position = 1
                    entry_price = current_price
            elif position == 1:
                if current_signal == -1: # Close Long
                    position = 0
                    pnl_pct = (current_price - entry_price) / entry_price * 100
                    trades.append(pnl_pct)
        
        # 統計
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "strategy": strategy_name,
                "total_trades": 0,
                "win_rate": 0.0,
                "total_return": 0.0,
                "avg_return": 0.0,
                "signal_quality": "無交易信號"
            }
            
        wins = [t for t in trades if t > 0]
        win_rate = (len(wins) / total_trades) * 100
        total_return = sum(trades)
        
        # 評分信號質量
        quality = "中性"
        if total_trades > 3:
            if win_rate > 60: quality = "高勝率"
            elif win_rate < 40: quality = "低勝率"
            
        return {
            "strategy": strategy_name,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "total_return": round(total_return, 2),
            "avg_return": round(total_return / total_trades, 2),
            "signal_quality": quality
        }

    @staticmethod
    def run_rsi_strategy(df: pd.DataFrame, period: int = 14, overbought: int = 70, oversold: int = 30) -> Dict:
        """RSI 逆勢策略: 超賣買入，超買賣出"""
        if 'RSI' not in df.columns:
            df.ta.rsi(length=period, append=True)
            
        rsi = df[f'RSI_{period}']
        
        # 1 = Buy, -1 = Sell, 0 = Hold
        signals = pd.Series(0, index=df.index)
        
        # 黃金交叉/死亡交叉邏輯 (或是簡單的閾值穿越)
        # 這裡用簡單閾值：低於30變買入，高於70變賣出
        signals[rsi < oversold] = 1
        signals[rsi > overbought] = -1
        
        return BacktestEngine.calculate_performance(signals, df['Close'], "RSI逆勢策略")

    @staticmethod
    def run_trend_following_strategy(df: pd.DataFrame, short_ma: int = 20, long_ma: int = 50) -> Dict:
        """均線趨勢策略: 黃金交叉買入，死亡交叉賣出"""
        # 確保指標存在
        sma_short = df.ta.sma(length=short_ma)
        sma_long = df.ta.sma(length=long_ma)
        
        signals = pd.Series(0, index=df.index)
        
        # 交叉判斷
        crossover = (sma_short > sma_long) & (sma_short.shift(1) <= sma_long.shift(1))
        crossunder = (sma_short < sma_long) & (sma_short.shift(1) >= sma_long.shift(1))
        
        signals[crossover] = 1
        signals[crossunder] = -1
        
        return BacktestEngine.calculate_performance(signals, df['Close'], "MA趨勢策略")
        
    @staticmethod
    def run_bollinger_reversion(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> Dict:
        """布林帶回歸策略: 突破下軌買入，突破上軌賣出"""
        # 確保指標存在 (pandas_ta 生成的列名通常是 BBL_length_std, BBU_length_std)
        if not any(col.startswith('BBL') for col in df.columns):
            df.ta.bbands(length=length, std=std, append=True)
            
        # 找到列名
        bbl_col = [c for c in df.columns if c.startswith(f'BBL_{length}')][0]
        bbu_col = [c for c in df.columns if c.startswith(f'BBU_{length}')][0]
        
        signals = pd.Series(0, index=df.index)
        signals[df['Close'] < df[bbl_col]] = 1
        signals[df['Close'] > df[bbu_col]] = -1
        
        return BacktestEngine.calculate_performance(signals, df['Close'], "布林帶回歸策略")

    def run_all_strategies(self, df: pd.DataFrame) -> List[Dict]:
        """執行所有預設策略的回測"""
        results = []
        try:
            results.append(self.run_rsi_strategy(df.copy()))
            results.append(self.run_trend_following_strategy(df.copy()))
            results.append(self.run_bollinger_reversion(df.copy()))
            
            # 排序：按總回報率降序
            results.sort(key=lambda x: x['total_return'], reverse=True)
            
            # 增加摘要
            best_strategy = results[0]
            summary = {
                "summary": f"歷史數據回測顯示，'{best_strategy['strategy']}' 表現最佳，勝率 {best_strategy['win_rate']}%，總回報 {best_strategy['total_return']}%。",
                "best_strategy_name": best_strategy['strategy'],
                "best_win_rate": best_strategy['win_rate']
            }
            results.insert(0, summary)
            
        except Exception as e:
            print(f"回測執行失敗: {e}")
            return [{"error": str(e)}]
            
        return results
