# -*- coding: utf-8 -*-
"""
Market Scanner - 窮舉回溯法找趨勢線
從最新點往回找，確保每條線都滿足嚴格條件
"""
import sys
import os
import pandas as pd
import numpy as np
import warnings
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.signal import argrelextrema
warnings.filterwarnings('ignore')

print("Initializing Exhaustive Pattern Scanner...", flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from data.data_fetcher import get_data_fetcher


class ExhaustiveTrendlineDetector:
    """
    窮舉回溯趨勢線檢測器
    
    算法：
    1. 從最新高點/低點開始
    2. 與第二個點連線，檢查是否所有K線實體都在線的正確側
    3. 如果通過，找第三個點（也在線上）
    4. 持續找更多點，同時確保線下/線上沒有實體突破
    5. 嘗試所有組合，選出「點數最多」的線
    """

    def __init__(self, order=8, tolerance=0.006):
        """
        參數：
        - order: scipy 轉折點檢測範圍（加大以找更重要的點）
        - tolerance: 點是否在線上的容差 (0.6% - 放寬以適應真實市場)
        """
        self.order = order
        self.tolerance = tolerance

    def find_pivot_highs(self, df):
        """找出所有波段高點"""
        highs = df['High'].values
        peak_indices = argrelextrema(highs, np.greater, order=self.order)[0]
        
        pivots = []
        for idx in peak_indices:
            if idx < len(df):
                pivots.append({
                    'index': int(idx),
                    'price': float(highs[idx])
                })
        
        return sorted(pivots, key=lambda x: x['index'])

    def find_pivot_lows(self, df):
        """找出所有波段低點"""
        lows = df['Low'].values
        valley_indices = argrelextrema(lows, np.less, order=self.order)[0]
        
        pivots = []
        for idx in valley_indices:
            if idx < len(df):
                pivots.append({
                    'index': int(idx),
                    'price': float(lows[idx])
                })
        
        return sorted(pivots, key=lambda x: x['index'])

    def check_no_body_penetration(self, df, p1, p2, line_type='resistance'):
        """
        檢查兩點之間是否有K線實體穿過
        
        返回：True = 沒有穿過（有效）, False = 有穿過（無效）
        """
        idx1, price1 = p1['index'], p1['price']
        idx2, price2 = p2['index'], p2['price']
        
        # 計算斜率和截距
        if idx2 == idx1:
            return False
        
        slope = (price2 - price1) / (idx2 - idx1)
        intercept = price1 - slope * idx1
        
        # 檢查兩點之間的所有K線
        start = min(idx1, idx2)
        end = max(idx1, idx2)
        
        for i in range(start, end + 1):
            line_price = slope * i + intercept
            candle = df.iloc[i]
            
            if line_type == 'resistance':
                # 壓力線：實體頂部不能超過線
                body_top = max(candle['Open'], candle['Close'])
                if body_top > line_price:
                    return False
            else:
                # 支撐線：實體底部不能低於線
                body_bottom = min(candle['Open'], candle['Close'])
                if body_bottom < line_price:
                    return False
        
        return True

    def is_point_on_line(self, point, slope, intercept):
        """檢查點是否在線上（容差內）"""
        expected_price = slope * point['index'] + intercept
        error = abs(point['price'] - expected_price) / point['price']
        return error < self.tolerance

    def find_all_points_on_line(self, pivots, slope, intercept):
        """找出所有在這條線上的點"""
        points_on_line = []
        for p in pivots:
            if self.is_point_on_line(p, slope, intercept):
                points_on_line.append(p)
        return points_on_line

    def check_line_validity_to_current(self, df, slope, intercept, start_idx, line_type='resistance'):
        """
        檢查從 start_idx 到最後一根K線，是否都沒有實體穿過
        
        這是關鍵：確保線延伸到「現在」都有效
        """
        end_idx = len(df) - 1
        
        for i in range(start_idx, end_idx + 1):
            line_price = slope * i + intercept
            candle = df.iloc[i]
            
            if line_type == 'resistance':
                body_top = max(candle['Open'], candle['Close'])
                if body_top > line_price:
                    return False, i  # 返回失效位置
            else:
                body_bottom = min(candle['Open'], candle['Close'])
                if body_bottom < line_price:
                    return False, i
        
        return True, end_idx

    def exhaustive_search_trendline(self, df, pivots, line_type='resistance'):
        """
        窮舉搜尋趨勢線 - 改進版
        
        改進：
        1. 移除時間限制 - 允許任意跨度的線
        2. 嘗試所有兩點組合（不只從最新點開始）
        3. 優先選擇「包含最新點」且「跨度最大」的線
        """
        if len(pivots) < 2:
            return None
        
        valid_lines = []
        current_idx = len(df) - 1
        
        # 找出最新的轉折點
        latest_pivot_idx = max(p['index'] for p in pivots)
        
        # 嘗試所有兩點組合
        for i in range(len(pivots)):
            for j in range(i + 1, len(pivots)):
                p1 = pivots[i]
                p2 = pivots[j]
                
                # 檢查兩點間是否有實體穿過
                if not self.check_no_body_penetration(df, p1, p2, line_type):
                    continue
                
                # 計算這條線的斜率和截距
                slope = (p2['price'] - p1['price']) / (p2['index'] - p1['index'])
                intercept = p1['price'] - slope * p1['index']
                
                # 找出所有在這條線上的點
                points_on_line = self.find_all_points_on_line(pivots, slope, intercept)
                
                # 必須至少有3個點
                if len(points_on_line) < 3:
                    continue
                
                # 檢查線延伸到當前是否仍然有效
                first_idx = min(p['index'] for p in points_on_line)
                is_valid, valid_end = self.check_line_validity_to_current(
                    df, slope, intercept, first_idx, line_type
                )
                
                if not is_valid:
                    continue
                
                # 計算跨度
                last_idx = max(p['index'] for p in points_on_line)
                span = last_idx - first_idx
                
                # 檢查是否包含最新的轉折點
                has_latest = (last_idx == latest_pivot_idx)
                
                # 計算最後一個點距離現在多近
                recency = current_idx - last_idx
                
                # 這是一條有效的線！
                valid_lines.append({
                    'slope': slope,
                    'intercept': intercept,
                    'points': sorted(points_on_line, key=lambda x: x['index']),
                    'count': len(points_on_line),
                    'span': span,
                    'first_idx': first_idx,
                    'valid_end': valid_end,
                    'is_active': (valid_end >= len(df) - 1),
                    'has_latest': has_latest,
                    'recency': recency
                })
        
        # 如果沒找到有效線
        if not valid_lines:
            return None
        
        # 排序策略：
        # 1. 優先包含最新轉折點的線
        # 2. 其次選跨度最大的
        # 3. 最後選點數最多的
        valid_lines.sort(key=lambda x: (x['has_latest'], x['span'], x['count']), reverse=True)
        
        return valid_lines[0]

    def is_valid_channel_pattern(self, resistance, support):
        """
        判斷是否為有效的通道形態
        
        過濾條件：
        1. 必須同時有上下軌
        2. 拒絕發散形態（喇叭狀）
        3. 接受：收斂（楔形、對稱三角）或平行（通道）
        """
        if not resistance or not support:
            return False
        
        # 計算上下軌的斜率
        upper_slope = resistance['slope']
        lower_slope = support['slope']
        
        # 計算在不同位置的價格差距（用於判斷是否發散）
        current_idx = min(resistance['valid_end'], support['valid_end'])
        first_idx = min(resistance['first_idx'], support['first_idx'])
        
        # 確保有足夠的跨度來判斷
        if current_idx - first_idx < 20:
            return False
        
        # 計算起點、中點、終點的通道寬度
        start_upper = upper_slope * first_idx + resistance['intercept']
        start_lower = lower_slope * first_idx + support['intercept']
        start_width = abs(start_upper - start_lower)
        
        mid_idx = (first_idx + current_idx) // 2
        mid_upper = upper_slope * mid_idx + resistance['intercept']
        mid_lower = lower_slope * mid_idx + support['intercept']
        mid_width = abs(mid_upper - mid_lower)
        
        end_upper = upper_slope * current_idx + resistance['intercept']
        end_lower = lower_slope * current_idx + support['intercept']
        end_width = abs(end_upper - end_lower)
        
        # 判斷是發散還是收斂
        # 如果終點寬度 > 起點寬度 * 1.15，視為發散（喇叭）
        if end_width > start_width * 1.15:
            return False
        
        # 如果中點寬度比起點和終點都大，也可能是喇叭的一種變形
        if mid_width > start_width * 1.1 and mid_width > end_width * 1.1:
            return False
        
        # 通過檢查：可以是收斂或平行
        return True
    
    def detect_patterns(self, df):
        """檢測壓力線和支撐線"""
        # 找轉折點
        swing_highs = self.find_pivot_highs(df)
        swing_lows = self.find_pivot_lows(df)
        
        # 窮舉搜尋
        resistance = self.exhaustive_search_trendline(df, swing_highs, 'resistance')
        support = self.exhaustive_search_trendline(df, swing_lows, 'support')
        
        # 檢查是否為有效通道形態（必須通過發散檢查）
        if not self.is_valid_channel_pattern(resistance, support):
            # 喇叭狀形態：不保留
            return None, None
        
        return resistance, support


class ChartDrawer:
    """圖表繪製器"""

    def draw_pattern_chart(self, df, resistance, support, symbol, timeframe, save_path):
        """繪製趨勢線圖"""
        fig, ax = plt.subplots(figsize=(20, 11))

        # 計算繪圖範圍
        start_idx = len(df) - 200
        
        if resistance:
            start_idx = min(start_idx, resistance['first_idx'] - 10)
        if support:
            start_idx = min(start_idx, support['first_idx'] - 10)
        
        start_idx = max(0, start_idx)
        
        # K線繪製
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            color = '#EF5350' if row['Close'] >= row['Open'] else '#26A69A'
            
            # 影線
            ax.plot([i, i], [row['Low'], row['High']], 
                   color=color, linewidth=1.2, alpha=0.7)
            
            # 實體
            body_h = abs(row['Close'] - row['Open'])
            body_b = min(row['Open'], row['Close'])
            rect = Rectangle((i - 0.4, body_b), 0.8, body_h,
                           facecolor=color, edgecolor=color, alpha=0.9)
            ax.add_patch(rect)

        # 繪製趨勢線
        def draw_trendline(line, color, label):
            if not line:
                return
            
            # 繪製範圍：從第一個點到有效終點
            draw_start = line['first_idx']
            draw_end = line['valid_end']
            
            # 如果仍有效，延伸10根預測
            if line['is_active']:
                display_end = draw_end + 10
            else:
                display_end = draw_end
            
            x = [draw_start, display_end]
            y = [line['slope'] * xi + line['intercept'] for xi in x]
            
            # 主線
            style = '-' if line['is_active'] else '--'
            ax.plot(x, y, color=color, linestyle=style, linewidth=3, 
                   alpha=0.9, label=f"{label} ({line['count']}點)")
            
            # 標記所有連接點
            for p in line['points']:
                ax.plot(p['index'], p['price'], 'o', color=color, 
                       markersize=10, markeredgewidth=2.5, markeredgecolor='white', zorder=5)
            
            # 如果被突破，標記突破位置
            if not line['is_active']:
                ax.axvline(x=draw_end + 1, color=color, 
                          linestyle=':', linewidth=2, alpha=0.7)
                ax.text(draw_end + 1, ax.get_ylim()[1] * 0.98, '突破', 
                       color=color, fontsize=10, ha='center', 
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            
            # 顯示終點價格
            end_price = line['slope'] * display_end + line['intercept']
            ax.text(display_end + 2, end_price, f"{end_price:.2f}", 
                   color=color, fontweight='bold', fontsize=12,
                   va='center', ha='left',
                   bbox=dict(boxstyle='round,pad=0.5', 
                   facecolor='white', edgecolor=color, linewidth=2, alpha=0.95))

        if resistance:
            draw_trendline(resistance, '#D32F2F', '壓力線')
        if support:
            draw_trendline(support, '#388E3C', '支撐線')

        # 圖表裝飾
        pattern_type = "未知形態"
        if resistance and support:
            upper_slope = resistance['slope']
            lower_slope = support['slope']
            
            # 計算通道寬度變化（判斷收斂/平行/發散）
            current_idx = min(resistance['valid_end'], support['valid_end'])
            first_idx = min(resistance['first_idx'], support['first_idx'])
            
            start_upper = upper_slope * first_idx + resistance['intercept']
            start_lower = lower_slope * first_idx + support['intercept']
            start_width = abs(start_upper - start_lower)
            
            end_upper = upper_slope * current_idx + resistance['intercept']
            end_lower = lower_slope * current_idx + support['intercept']
            end_width = abs(end_upper - end_lower)
            
            width_ratio = end_width / start_width if start_width > 0 else 1
            
            # 判斷形態類型
            if abs(upper_slope) < 0.05 and abs(lower_slope) < 0.05:
                pattern_type = "矩形通道"
            elif upper_slope > 0 and lower_slope > 0:
                # 兩條線都向上
                if width_ratio < 0.85:
                    pattern_type = "上升楔形(收斂)"
                elif width_ratio < 1.15:
                    pattern_type = "上升通道(平行)"
                else:
                    pattern_type = "上升喇叭(發散)⚠"
            elif upper_slope < 0 and lower_slope < 0:
                # 兩條線都向下
                if width_ratio < 0.85:
                    pattern_type = "下降楔形(收斂)"
                elif width_ratio < 1.15:
                    pattern_type = "下降通道(平行)"
                else:
                    pattern_type = "下降喇叭(發散)⚠"
            elif upper_slope < 0 and lower_slope > 0:
                # 對稱三角：上降下升
                if width_ratio < 0.85:
                    pattern_type = "對稱三角(收斂)"
                else:
                    pattern_type = "收縮後擴張⚠"
            elif upper_slope > 0 and lower_slope < 0:
                # 擴張三角：上升下降
                pattern_type = "擴張三角(發散)⚠"
        
        status = []
        if resistance:
            st = '✓活躍' if resistance['is_active'] else '✗突破'
            span_days = resistance['span']
            status.append(f"壓力:{st}({resistance['count']}點,跨{span_days}根)")
        else:
            status.append("壓力:無")
        
        if support:
            st = '✓活躍' if support['is_active'] else '✗跌破'
            span_days = support['span']
            status.append(f"支撐:{st}({support['count']}點,跨{span_days}根)")
        else:
            status.append("支撐:無")
        
        title = f"{symbol} | {timeframe} | {pattern_type} | {' | '.join(status)}"
        
        ax.set_title(title, fontsize=15, fontweight='bold', pad=20)
        ax.set_xlabel('K線索引', fontsize=12)
        ax.set_ylabel('價格', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)
        ax.legend(loc='upper left', fontsize=12, framealpha=0.95)
        
        ax.set_xlim(start_idx - 5, len(df) + 15)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)


class MarketScanner:
    """市場掃描器"""

    def __init__(self, lookback=800):
        self.lookback = lookback
        self.detector = ExhaustiveTrendlineDetector(order=8, tolerance=0.006)
        self.drawer = ChartDrawer()
        self.fetcher = get_data_fetcher("okx")

    def scan(self, symbols, timeframes=["15m", "1h", "4h"]):
        """掃描市場"""
        print(f"\n{'='*80}")
        print(f"  窮舉回溯法趨勢線掃描器 (Exhaustive Backtracking)")
        print(f"  方法: 從最新點往回找，確保無實體穿越")
        print(f"  回溯: {self.lookback} 根K線")
        print(f"{'='*80}\n")

        os.makedirs("pattern_charts", exist_ok=True)

        for symbol in symbols:
            print(f"\n{'─'*80}")
            print(f"📊 {symbol}")
            print(f"{'─'*80}")

            for timeframe in timeframes:
                try:
                    df = self.fetcher.get_historical_klines(symbol, timeframe, self.lookback)

                    if df is None or len(df) < 100:
                        print(f"  [{timeframe}] ⚠ 數據不足")
                        continue

                    # 檢測
                    resistance, support = self.detector.detect_patterns(df)

                    # 輸出
                    result = []
                    pattern_info = ""
                    
                    if resistance and support:
                        upper_slope = resistance['slope']
                        lower_slope = support['slope']
                        
                        # 簡單判斷形態
                        if upper_slope > 0 and lower_slope > 0:
                            if upper_slope < lower_slope:
                                pattern_info = "上升楔形"
                            else:
                                pattern_info = "上升通道" if abs(upper_slope - lower_slope) / lower_slope < 0.2 else "⚠喇叭"
                        elif upper_slope < 0 and lower_slope < 0:
                            if upper_slope > lower_slope:
                                pattern_info = "下降楔形"
                            else:
                                pattern_info = "下降通道" if abs(upper_slope - lower_slope) / abs(lower_slope) < 0.2 else "⚠喇叭"
                        else:
                            pattern_info = "對稱三角" if upper_slope * lower_slope < 0 else "⚠喇叭"
                    
                    if resistance:
                        status = "✓" if resistance['is_active'] else "✗"
                        result.append(f"壓:{status}({resistance['count']}點/跨{resistance['span']})")
                    else:
                        result.append("壓:無")
                    
                    if support:
                        status = "✓" if support['is_active'] else "✗"
                        result.append(f"撐:{status}({support['count']}點/跨{support['span']})")
                    else:
                        result.append("撐:無")

                    output = f"  [{timeframe}] {' | '.join(result)}"
                    if pattern_info:
                        output += f" | {pattern_info}"
                    print(output)

                    # 繪圖
                    if resistance or support:
                        save_path = f"pattern_charts/{symbol.replace('-', '_')}_{timeframe}_exhaustive.png"
                        self.drawer.draw_pattern_chart(df, resistance, support,
                                                       symbol, timeframe, save_path)

                except Exception as e:
                    print(f"  [{timeframe}] ✗ 錯誤: {str(e)}")
                    import traceback
                    traceback.print_exc()

        print(f"\n{'='*80}")
        print(f"  掃描完成！")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    targets = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
    scanner = MarketScanner(lookback=500)
    scanner.scan(targets, timeframes=["15m", "1h", "4h"])