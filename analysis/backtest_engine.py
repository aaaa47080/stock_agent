"""
專業級回測引擎
基於金融業界標準的技術策略回測系統

支持策略：
- RSI 逆勢策略 (標準 30/70)
- MACD 趨勢策略 (12/26/9)
- 均線交叉策略 (SMA 20/50, EMA 12/26)
- 布林帶回歸策略 (20, 2σ)
- KDJ 隨機指標策略 (9/3/3)

風險指標：
- 勝率 (Win Rate)
- 盈虧比 (Profit Factor)
- 最大回撤 (Max Drawdown)
- 夏普比率 (Sharpe Ratio)
"""

import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TradeRecord:
    """交易記錄"""
    entry_price: float
    exit_price: float
    pnl_pct: float
    holding_bars: int


class BacktestEngine:
    """
    專業級向量回測引擎
    支持多策略、多週期、風險指標計算
    """

    # ========================================
    # 核心計算方法
    # ========================================

    @staticmethod
    def calculate_performance(
        signals: pd.Series,
        close_prices: pd.Series,
        strategy_name: str,
        include_risk_metrics: bool = True
    ) -> Dict:
        """
        計算策略表現（含風險指標）

        Args:
            signals: 1 (Buy), -1 (Sell), 0 (Hold)
            close_prices: 收盤價序列
            strategy_name: 策略名稱
            include_risk_metrics: 是否計算風險指標

        Returns:
            策略表現字典
        """
        position = 0
        entry_price = 0
        entry_idx = 0
        trades: List[TradeRecord] = []
        equity_curve = [100.0]  # 初始資金 100

        sig_arr = signals.values
        price_arr = close_prices.values

        for i in range(len(sig_arr) - 1):
            current_signal = sig_arr[i]
            current_price = price_arr[i]

            if position == 0:
                if current_signal == 1:  # 開多
                    position = 1
                    entry_price = current_price
                    entry_idx = i
            elif position == 1:
                if current_signal == -1:  # 平倉
                    position = 0
                    pnl_pct = (current_price - entry_price) / entry_price * 100
                    trades.append(TradeRecord(
                        entry_price=entry_price,
                        exit_price=current_price,
                        pnl_pct=pnl_pct,
                        holding_bars=i - entry_idx
                    ))
                    # 更新權益曲線
                    equity_curve.append(equity_curve[-1] * (1 + pnl_pct / 100))

        # 基礎統計
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "strategy": strategy_name,
                "total_trades": 0,
                "win_rate": 0.0,
                "total_return": 0.0,
                "avg_return": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "avg_holding_bars": 0,
                "signal_quality": "無交易信號"
            }

        # 勝率計算
        wins = [t for t in trades if t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct < 0]
        win_rate = (len(wins) / total_trades) * 100

        # 收益計算
        total_return = sum(t.pnl_pct for t in trades)
        avg_return = total_return / total_trades

        # 盈虧比 (Profit Factor)
        gross_profit = sum(t.pnl_pct for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_pct for t in losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit

        # 最大回撤 (Max Drawdown)
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdowns = (equity_series - rolling_max) / rolling_max * 100
        max_drawdown = abs(drawdowns.min())

        # 夏普比率 (簡化版，假設無風險利率為 0)
        returns = pd.Series([t.pnl_pct for t in trades])
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

        # 平均持倉時間
        avg_holding_bars = sum(t.holding_bars for t in trades) / total_trades

        # 信號品質評估
        quality = BacktestEngine._evaluate_signal_quality(
            win_rate, profit_factor, max_drawdown, total_trades
        )

        return {
            "strategy": strategy_name,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "total_return": round(total_return, 2),
            "avg_return": round(avg_return, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "avg_holding_bars": round(avg_holding_bars, 1),
            "signal_quality": quality
        }

    @staticmethod
    def _evaluate_signal_quality(
        win_rate: float,
        profit_factor: float,
        max_drawdown: float,
        total_trades: int
    ) -> str:
        """評估信號品質"""
        if total_trades < 3:
            return "樣本不足"

        score = 0
        # 勝率評分
        if win_rate >= 60:
            score += 2
        elif win_rate >= 50:
            score += 1

        # 盈虧比評分
        if profit_factor >= 2.0:
            score += 2
        elif profit_factor >= 1.5:
            score += 1

        # 回撤評分
        if max_drawdown <= 10:
            score += 2
        elif max_drawdown <= 20:
            score += 1

        # 綜合評級
        if score >= 5:
            return "優秀"
        elif score >= 3:
            return "良好"
        elif score >= 1:
            return "中性"
        else:
            return "偏弱"

    # ========================================
    # 策略實現
    # ========================================

    @staticmethod
    def run_rsi_strategy(
        df: pd.DataFrame,
        period: int = 14,
        overbought: int = 70,
        oversold: int = 30
    ) -> Dict:
        """
        RSI 逆勢策略（業界標準）
        - 超賣區 (<30) 買入
        - 超買區 (>70) 賣出
        """
        df = df.copy()
        rsi_col = f'RSI_{period}'
        if rsi_col not in df.columns:
            df.ta.rsi(length=period, append=True)

        rsi = df[rsi_col]
        signals = pd.Series(0, index=df.index)
        signals[rsi < oversold] = 1
        signals[rsi > overbought] = -1

        return BacktestEngine.calculate_performance(
            signals, df['Close'], f"RSI逆勢({oversold}/{overbought})"
        )

    @staticmethod
    def run_macd_strategy(
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict:
        """
        MACD 趨勢策略（業界標準 12/26/9）
        - MACD 線上穿信號線：買入
        - MACD 線下穿信號線：賣出
        """
        df = df.copy()
        macd = df.ta.macd(fast=fast, slow=slow, signal=signal)

        if macd is None or macd.empty:
            return {"strategy": "MACD策略", "total_trades": 0, "signal_quality": "計算失敗"}

        macd_line = macd[f'MACD_{fast}_{slow}_{signal}']
        signal_line = macd[f'MACDs_{fast}_{slow}_{signal}']

        signals = pd.Series(0, index=df.index)

        # 金叉（MACD 上穿信號線）
        golden_cross = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        # 死叉（MACD 下穿信號線）
        death_cross = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

        signals[golden_cross] = 1
        signals[death_cross] = -1

        return BacktestEngine.calculate_performance(
            signals, df['Close'], f"MACD({fast}/{slow}/{signal})"
        )

    @staticmethod
    def run_ema_crossover_strategy(
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26
    ) -> Dict:
        """
        EMA 均線交叉策略
        - 短期 EMA 上穿長期 EMA：買入
        - 短期 EMA 下穿長期 EMA：賣出
        """
        df = df.copy()
        ema_fast = df.ta.ema(length=fast)
        ema_slow = df.ta.ema(length=slow)

        signals = pd.Series(0, index=df.index)

        golden_cross = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        death_cross = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        signals[golden_cross] = 1
        signals[death_cross] = -1

        return BacktestEngine.calculate_performance(
            signals, df['Close'], f"EMA交叉({fast}/{slow})"
        )

    @staticmethod
    def run_sma_trend_strategy(
        df: pd.DataFrame,
        short_ma: int = 20,
        long_ma: int = 50
    ) -> Dict:
        """
        SMA 趨勢策略（經典 20/50）
        - 黃金交叉：買入
        - 死亡交叉：賣出
        """
        df = df.copy()
        sma_short = df.ta.sma(length=short_ma)
        sma_long = df.ta.sma(length=long_ma)

        signals = pd.Series(0, index=df.index)

        crossover = (sma_short > sma_long) & (sma_short.shift(1) <= sma_long.shift(1))
        crossunder = (sma_short < sma_long) & (sma_short.shift(1) >= sma_long.shift(1))

        signals[crossover] = 1
        signals[crossunder] = -1

        return BacktestEngine.calculate_performance(
            signals, df['Close'], f"SMA趨勢({short_ma}/{long_ma})"
        )

    @staticmethod
    def run_bollinger_reversion(
        df: pd.DataFrame,
        length: int = 20,
        std: float = 2.0
    ) -> Dict:
        """
        布林帶回歸策略
        - 價格觸及下軌：買入
        - 價格觸及上軌：賣出
        """
        df = df.copy()
        bbands = df.ta.bbands(length=length, std=std)

        if bbands is None or bbands.empty:
            return {"strategy": "布林帶策略", "total_trades": 0, "signal_quality": "計算失敗"}

        # 找到正確的列名（pandas_ta 的列名格式可能不同）
        bbl_cols = [c for c in bbands.columns if c.startswith('BBL')]
        bbu_cols = [c for c in bbands.columns if c.startswith('BBU')]

        if not bbl_cols or not bbu_cols:
            return {"strategy": "布林帶策略", "total_trades": 0, "signal_quality": "計算失敗"}

        bbl_col = bbl_cols[0]
        bbu_col = bbu_cols[0]

        signals = pd.Series(0, index=df.index)
        signals[df['Close'] < bbands[bbl_col]] = 1
        signals[df['Close'] > bbands[bbu_col]] = -1

        return BacktestEngine.calculate_performance(
            signals, df['Close'], f"布林帶回歸({length},{std}σ)"
        )

    @staticmethod
    def run_kdj_strategy(
        df: pd.DataFrame,
        k_period: int = 9,
        d_period: int = 3,
        overbought: int = 80,
        oversold: int = 20
    ) -> Dict:
        """
        KDJ 隨機指標策略（業界標準 9/3/3）
        - K 線在超賣區上穿 D 線：買入
        - K 線在超買區下穿 D 線：賣出
        """
        df = df.copy()
        stoch = df.ta.stoch(k=k_period, d=d_period)

        if stoch is None or stoch.empty:
            return {"strategy": "KDJ策略", "total_trades": 0, "signal_quality": "計算失敗"}

        k_col = f'STOCHk_{k_period}_{d_period}_3'
        d_col = f'STOCHd_{k_period}_{d_period}_3'

        k_line = stoch[k_col]
        d_line = stoch[d_col]

        signals = pd.Series(0, index=df.index)

        # 超賣區金叉
        buy_signal = (k_line > d_line) & (k_line.shift(1) <= d_line.shift(1)) & (k_line < oversold + 20)
        # 超買區死叉
        sell_signal = (k_line < d_line) & (k_line.shift(1) >= d_line.shift(1)) & (k_line > overbought - 20)

        signals[buy_signal] = 1
        signals[sell_signal] = -1

        return BacktestEngine.calculate_performance(
            signals, df['Close'], f"KDJ({k_period}/{d_period})"
        )

    @staticmethod
    def run_rsi_macd_combo_strategy(df: pd.DataFrame) -> Dict:
        """
        RSI + MACD 組合策略（多指標確認）
        - RSI < 40 且 MACD 金叉：買入
        - RSI > 60 且 MACD 死叉：賣出
        """
        df = df.copy()

        # 計算 RSI
        df.ta.rsi(length=14, append=True)
        rsi = df['RSI_14']

        # 計算 MACD
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is None:
            return {"strategy": "RSI+MACD組合", "total_trades": 0, "signal_quality": "計算失敗"}

        macd_line = macd['MACD_12_26_9']
        signal_line = macd['MACDs_12_26_9']

        signals = pd.Series(0, index=df.index)

        # 買入：RSI 偏低 + MACD 金叉
        macd_golden = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        buy_signal = macd_golden & (rsi < 40)

        # 賣出：RSI 偏高 + MACD 死叉
        macd_death = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        sell_signal = macd_death & (rsi > 60)

        signals[buy_signal] = 1
        signals[sell_signal] = -1

        return BacktestEngine.calculate_performance(
            signals, df['Close'], "RSI+MACD組合"
        )

    # ========================================
    # 執行方法
    # ========================================

    def run_all_strategies(self, df: pd.DataFrame) -> List[Dict]:
        """執行所有策略的回測"""
        results = []
        try:
            # 執行所有策略
            results.append(self.run_rsi_strategy(df.copy()))
            results.append(self.run_macd_strategy(df.copy()))
            results.append(self.run_ema_crossover_strategy(df.copy()))
            results.append(self.run_sma_trend_strategy(df.copy()))
            results.append(self.run_bollinger_reversion(df.copy()))
            results.append(self.run_kdj_strategy(df.copy()))
            results.append(self.run_rsi_macd_combo_strategy(df.copy()))

            # 過濾有效策略
            valid_strategies = [r for r in results if r.get('total_trades', 0) > 0]

            # 按總回報率排序
            results.sort(key=lambda x: x.get('total_return', 0), reverse=True)

            # 生成摘要
            summary = self._generate_summary(results, valid_strategies, len(df))
            results.insert(0, summary)

        except Exception as e:
            print(f"回測執行失敗: {e}")
            import traceback
            traceback.print_exc()
            return [{"error": str(e)}]

        return results

    def run_multi_timeframe_backtest(
        self,
        symbol: str,
        exchange: str,
        intervals: List[str] = ["4h", "1d"],
        limit: int = 200
    ) -> Dict[str, List[Dict]]:
        """
        多週期回測

        Args:
            symbol: 交易對
            exchange: 交易所
            intervals: 時間週期列表
            limit: K線數量

        Returns:
            {interval: [回測結果]}
        """
        from data.data_processor import fetch_and_process_klines

        results = {}
        for interval in intervals:
            try:
                df, _ = fetch_and_process_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    market_type="spot",
                    exchange=exchange
                )
                results[interval] = self.run_all_strategies(df)
            except Exception as e:
                results[interval] = [{"error": str(e)}]

        return results

    def _generate_summary(
        self,
        all_results: List[Dict],
        valid_strategies: List[Dict],
        data_length: int
    ) -> Dict:
        """生成回測摘要"""
        if not valid_strategies:
            return {
                "summary": f"回測期間（{data_length} 根K線）內，所有策略均未產生有效交易信號。市場可能處於強趨勢或盤整狀態。",
                "best_strategy_name": "無",
                "best_win_rate": 0,
                "best_profit_factor": 0,
                "total_strategies_tested": len(all_results),
                "strategies_with_signals": 0,
                "has_valid_trades": False
            }

        # 找出最佳策略（綜合評分）
        def score_strategy(s: Dict) -> float:
            wr = s.get('win_rate', 0)
            pf = s.get('profit_factor', 0)
            ret = s.get('total_return', 0)
            mdd = s.get('max_drawdown', 100)
            # 綜合評分 = 勝率*0.3 + 盈虧比*20 + 回報*0.5 - 回撤*0.5
            return wr * 0.3 + pf * 20 + ret * 0.5 - mdd * 0.5

        valid_strategies.sort(key=score_strategy, reverse=True)
        best = valid_strategies[0]

        # 計算整體統計
        avg_win_rate = sum(s.get('win_rate', 0) for s in valid_strategies) / len(valid_strategies)
        avg_profit_factor = sum(s.get('profit_factor', 0) for s in valid_strategies) / len(valid_strategies)

        return {
            "summary": (
                f"回測 {data_length} 根K線，測試 {len(all_results)} 個策略，"
                f"{len(valid_strategies)} 個產生交易信號。"
                f"最佳策略：'{best['strategy']}'，"
                f"勝率 {best.get('win_rate', 0)}%，"
                f"盈虧比 {best.get('profit_factor', 0)}，"
                f"總回報 {best.get('total_return', 0)}%，"
                f"最大回撤 {best.get('max_drawdown', 0)}%。"
            ),
            "best_strategy_name": best['strategy'],
            "best_win_rate": best.get('win_rate', 0),
            "best_profit_factor": best.get('profit_factor', 0),
            "best_total_return": best.get('total_return', 0),
            "best_max_drawdown": best.get('max_drawdown', 0),
            "avg_win_rate": round(avg_win_rate, 2),
            "avg_profit_factor": round(avg_profit_factor, 2),
            "total_strategies_tested": len(all_results),
            "strategies_with_signals": len(valid_strategies),
            "has_valid_trades": True
        }


# 向後兼容：保留舊的函數名
def run_trend_following_strategy(df: pd.DataFrame, short_ma: int = 20, long_ma: int = 50) -> Dict:
    """向後兼容的均線策略"""
    return BacktestEngine.run_sma_trend_strategy(df, short_ma, long_ma)
