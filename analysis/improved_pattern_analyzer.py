"""
改进的三角形态分析器
使用归一化的斜率来检测形态,解决价格范围差异导致的检测失败问题
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class TriangleType(Enum):
    ASCENDING = "ascending"              # 上升三角形
    DESCENDING = "descending"            # 下降三角形
    CONSOLIDATION = "consolidation"      # 水平震荡区间
    SYMMETRIC = "symmetric"              # 对称三角形
    RISING_CHANNEL = "rising_channel"    # 上升通道
    FALLING_CHANNEL = "falling_channel"  # 下降通道
    NONE = "none"


@dataclass
class TrianglePattern:
    """三角形型态资料结构"""
    pattern_type: TriangleType
    start_idx: int
    end_idx: int
    high_points: List[Tuple[int, float]]
    low_points: List[Tuple[int, float]]
    confidence: float
    size: float
    trendline_high: Tuple[float, float]  # (斜率, 截距)
    trendline_low: Tuple[float, float]   # (斜率, 截距)
    normalized_slope_high: float         # 归一化斜率(百分比/索引)
    normalized_slope_low: float          # 归一化斜率(百分比/索引)


class ImprovedPatternAnalyzer:
    """
    改进的形态分析器
    使用归一化斜率进行检测
    """

    def __init__(self, min_points: int = 3, min_size_threshold: float = 0.02):
        self.min_points = min_points
        self.min_size_threshold = min_size_threshold

    def find_high_low_points(self, df: pd.DataFrame, window: int = 10) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        寻找高点和低点 - 增强版
        忽略传入的 window 参数，使用较小的固定窗口 (3) 來捕捉所有的潛在轉折點 (Pivots)。
        這樣可以避免因為窗口過大而漏掉形態內部的關鍵點。
        """
        highs = df['High'].values
        lows = df['Low'].values

        high_points = []
        low_points = []
        
        # 使用固定小窗口 = 3
        # 這意味著只要一個點比前後 3 個點都高，就算是一個候選高點
        search_window = 3

        for i in range(search_window, len(df) - search_window):
            # 局部高点
            if (highs[i] == max(highs[i - search_window:i + search_window + 1]) and
                highs[i] > highs[i - 1] and highs[i] > highs[i + 1]):
                high_points.append((i, highs[i]))

            # 局部低点
            if (lows[i] == min(lows[i - search_window:i + search_window + 1]) and
                lows[i] < lows[i - 1] and lows[i] < lows[i + 1]):
                low_points.append((i, lows[i]))

        return high_points, low_points

    def fit_upper_envelope(self, points: List[Tuple[int, float]], df: pd.DataFrame,
                          pattern_start_idx: int = None, pattern_end_idx: int = None) -> Optional[Tuple[float, float]]:
        """
        拟合上轨（压力线） - 严格遵循「实体不出界，影线可穿透」+ 「两点/三点一线」规则

        核心规则：
        1. 铁律：趋势线绝对不能切过形态范围内任何一根 K 线的实体
        2. 有效连接点：至少 2 个以上（Tip Touch 或 Wick Cut）
        3. 点位分散度：连接点跨度必须占形态长度的 40% 以上
        4. 评分：连接点数量 > 跨度 > 影线穿透惩罚

        Args:
            points: 高点列表
            df: K线数据
            pattern_start_idx: 形态起始索引（如果为None，使用points范围）
            pattern_end_idx: 形态结束索引（如果为None，使用points范围）
        """
        if len(points) < 2:
            return None

        best_line = None
        max_score = -float('inf')

        # 形态范围：优先使用传入的统一范围，否则使用候选点范围
        if pattern_start_idx is None or pattern_end_idx is None:
            start_idx = points[0][0]
            end_idx = points[-1][0]
        else:
            start_idx = pattern_start_idx
            end_idx = pattern_end_idx

        pattern_len = end_idx - start_idx

        if pattern_len < 5:
            return None

        # 预先提取形态范围内所有 K 线的数据
        subset = df.iloc[start_idx : end_idx + 1]
        all_opens = subset['Open'].values
        all_closes = subset['Close'].values
        all_highs = subset['High'].values
        all_body_tops = np.maximum(all_opens, all_closes)

        # 提取高点的索引集合，用于区分高点和普通K线
        high_point_indices = set([p[0] for p in points])

        # 穷举所有候选点对
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                p1 = points[i]
                p2 = points[j]

                # 基本跨度检查
                if p2[0] - p1[0] < 5:
                    continue

                # 计算趋势线参数
                slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
                intercept = p1[1] - slope * p1[0]

                # === 规则 1：全局实体检查（允许少量违规） ===
                # 计算形态范围内每一根 K 线的预测值
                indices = np.arange(start_idx, end_idx + 1)
                predicted_line = slope * indices + intercept

                # 检查：允许少量实体突破（最多10%的K线）
                tolerance = predicted_line * 0.002  # 0.2% 容差
                violations = np.sum(all_body_tops > predicted_line + tolerance)
                max_violations = max(2, int(len(all_body_tops) * 0.1))
                if violations > max_violations:
                    continue

                # === 规则 2：统计有效连接点（优先考虑高点） ===
                # 先统计高点（转折点）的连接
                pivot_connections = 0
                pivot_touch_indices = []

                for k in range(len(all_highs)):
                    abs_idx = start_idx + k

                    # 只检查高点（转折点）
                    if abs_idx in high_point_indices:
                        high = all_highs[k]
                        body_top = all_body_tops[k]
                        predicted = predicted_line[k]

                        # A 类：Tip Touch（高点刚好碰到趋势线）
                        diff_high = abs(high - predicted)
                        if diff_high <= high * 0.01:  # 1% 容差
                            pivot_connections += 1
                            pivot_touch_indices.append(abs_idx)
                        # B 类：Wick Cut（趋势线从影线中间穿过）
                        elif body_top < predicted < high:
                            pivot_connections += 1
                            pivot_touch_indices.append(abs_idx)
                        # C 类：近距离（在1.5%范围内）
                        elif diff_high <= high * 0.015:
                            pivot_connections += 0.5
                            pivot_touch_indices.append(abs_idx)

                # === 规则 2.1：至少 2 个高点连接 ===
                if pivot_connections < 2:
                    continue

                # === 规则 3：点位分散度检查（基于高点） ===
                if len(pivot_touch_indices) < 2:
                    continue

                spread = max(pivot_touch_indices) - min(pivot_touch_indices)
                if spread < pattern_len * 0.3:  # 降低到30%
                    # 分散度不足
                    continue

                # === 规则 5：评分算法 ===
                span = p2[0] - p1[0]
                # 高点连接奖励(+1000/点) + 跨度奖励(+5/单位)
                score = (pivot_connections * 1000) + (span * 5)

                if score > max_score:
                    max_score = score
                    best_line = (slope, intercept)

        return best_line

    def fit_lower_envelope(self, points: List[Tuple[int, float]], df: pd.DataFrame,
                          pattern_start_idx: int = None, pattern_end_idx: int = None) -> Optional[Tuple[float, float]]:
        """
        拟合下轨（支撑线） - 严格遵循「实体不出界，影线可穿透」+ 「两点/三点一线」规则

        核心规则：
        1. 铁律：趋势线绝对不能切过形态范围内任何一根 K 线的实体
        2. 有效连接点：至少 2 个以上（Tip Touch 或 Wick Cut）
        3. 点位分散度：连接点跨度必须占形态长度的 40% 以上
        4. 评分：连接点数量 > 跨度 > 影线穿透惩罚

        Args:
            points: 低点列表
            df: K线数据
            pattern_start_idx: 形态起始索引（如果为None，使用points范围）
            pattern_end_idx: 形态结束索引（如果为None，使用points范围）
        """
        if len(points) < 2:
            return None

        best_line = None
        max_score = -float('inf')

        # 形态范围：优先使用传入的统一范围，否则使用候选点范围
        if pattern_start_idx is None or pattern_end_idx is None:
            start_idx = points[0][0]
            end_idx = points[-1][0]
        else:
            start_idx = pattern_start_idx
            end_idx = pattern_end_idx

        pattern_len = end_idx - start_idx

        if pattern_len < 5:
            return None

        # 预先提取形态范围内所有 K 线的数据
        subset = df.iloc[start_idx : end_idx + 1]
        all_opens = subset['Open'].values
        all_closes = subset['Close'].values
        all_lows = subset['Low'].values
        all_body_bottoms = np.minimum(all_opens, all_closes)

        # 提取低点的索引集合，用于区分低点和普通K线
        low_point_indices = set([p[0] for p in points])

        # 穷举所有候选点对
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                p1 = points[i]
                p2 = points[j]

                # 基本跨度检查
                if p2[0] - p1[0] < 5:
                    continue

                # 计算趋势线参数
                slope = (p2[1] - p1[1]) / (p2[0] - p1[0])
                intercept = p1[1] - slope * p1[0]

                # === 规则 1：全局实体检查（允许少量违规） ===
                # 计算形态范围内每一根 K 线的预测值
                indices = np.arange(start_idx, end_idx + 1)
                predicted_line = slope * indices + intercept

                # 检查：允许少量实体突破（最多10%的K线）
                tolerance = predicted_line * 0.002  # 0.2% 容差
                violations = np.sum(all_body_bottoms < predicted_line - tolerance)
                max_violations = max(2, int(len(all_body_bottoms) * 0.1))
                if violations > max_violations:
                    continue

                # === 规则 2：统计有效连接点（优先考虑低点） ===
                # 先统计低点（转折点）的连接
                pivot_connections = 0
                pivot_touch_indices = []

                for k in range(len(all_lows)):
                    abs_idx = start_idx + k

                    # 只检查低点（转折点）
                    if abs_idx in low_point_indices:
                        low = all_lows[k]
                        body_bottom = all_body_bottoms[k]
                        predicted = predicted_line[k]

                        # A 类：Tip Touch（低点刚好碰到趋势线）
                        diff_low = abs(low - predicted)
                        if diff_low <= low * 0.01:  # 1% 容差
                            pivot_connections += 1
                            pivot_touch_indices.append(abs_idx)
                        # B 类：Wick Cut（趋势线从影线中间穿过）
                        elif low < predicted < body_bottom:
                            pivot_connections += 1
                            pivot_touch_indices.append(abs_idx)
                        # C 类：近距离（在1.5%范围内）
                        elif diff_low <= low * 0.015:
                            pivot_connections += 0.5
                            pivot_touch_indices.append(abs_idx)

                # === 规则 2.1：至少 2 个低点连接 ===
                if pivot_connections < 2:
                    continue

                # === 规则 3：点位分散度检查（基于低点） ===
                if len(pivot_touch_indices) < 2:
                    continue

                spread = max(pivot_touch_indices) - min(pivot_touch_indices)
                if spread < pattern_len * 0.3:  # 降低到30%
                    # 分散度不足
                    continue

                # === 规则 5：评分算法 ===
                span = p2[0] - p1[0]
                # 低点连接奖励(+1000/点) + 跨度奖励(+5/单位)
                score = (pivot_connections * 1000) + (span * 5)

                if score > max_score:
                    max_score = score
                    best_line = (slope, intercept)

        return best_line

    def calculate_normalized_slope(self, points: List[Tuple[int, float]], slope: float) -> float:
        """
        计算归一化斜率(百分比变化率/索引)

        归一化斜率 = (斜率 * 索引范围) / 平均价格
        这样可以将斜率转换为每个索引单位的百分比变化
        """
        if len(points) < 2:
            return 0.0

        prices = [p[1] for p in points]
        avg_price = np.mean(prices)

        if avg_price == 0:
            return 0.0

        # 归一化斜率 = 斜率 / 平均价格 (转换为百分比变化率)
        normalized_slope = slope / avg_price

        return normalized_slope

    def calculate_confidence(self, points: List[Tuple[int, float]], slope: float, intercept: float, threshold: float = 0.02) -> float:
        """计算趋势线拟合的信心度"""
        if len(points) < 2:
            return 0.0

        indices = np.array([p[0] for p in points])
        actual_prices = np.array([p[1] for p in points])
        predicted_prices = slope * indices + intercept

        # 计算平均绝对百分比误差(MAPE)
        mape = np.mean(np.abs((actual_prices - predicted_prices) / actual_prices))

        # 转换为信心度
        confidence = max(0.0, min(1.0, 1.0 - (mape / threshold)))

        return confidence

    def validate_pattern_with_candle_bodies(self, df: pd.DataFrame, pattern_start: int, pattern_end: int,
                                           slope_high: float, intercept_high: float,
                                           slope_low: float, intercept_low: float, debug: bool = False) -> bool:
        """
        验证形态：检查K线实体是否都在通道内（允许影线突破）

        Args:
            df: K线数据
            pattern_start: 形态起始索引
            pattern_end: 形态结束索引
            slope_high: 高点趋势线斜率
            intercept_high: 高点趋势线截距
            slope_low: 低点趋势线斜率
            intercept_low: 低点趋势线截距
            debug: 是否打印调试信息

        Returns:
            True if 所有K线实体都在通道内（0容忍）
        """
        violation_count = 0
        total_candles = 0
        violations = []

        for idx in range(pattern_start, min(pattern_end + 1, len(df))):
            row = df.iloc[idx]
            open_price = row['Open']
            close_price = row['Close']

            # K线实体的上下边界
            body_high = max(open_price, close_price)
            body_low = min(open_price, close_price)

            # 计算此位置的通道上下轨
            predicted_high = slope_high * idx + intercept_high
            predicted_low = slope_low * idx + intercept_low

            # 检查实体是否突破通道（严格模式：不允许实体突破，仅允许影线突破）
            tolerance = 0.0

            violated = False
            if body_high > predicted_high + tolerance:
                violation_count += 1
                violated = True
                if debug:
                    violations.append(f"Bar{idx}: body_high{body_high:.2f} > upper{predicted_high:.2f}")
            if body_low < predicted_low - tolerance:
                violation_count += 1
                violated = True
                if debug:
                    violations.append(f"Bar{idx}: body_low{body_low:.2f} < lower{predicted_low:.2f}")

            total_candles += 1

        max_allowed_violations = max(3, int(total_candles * 0.25))  # 允许25%的违规

        if debug and violation_count > 0:
            print(f"      Validation: {violation_count}/{total_candles} bars violated (max: {max_allowed_violations})")
            for v in violations[:3]:
                print(f"        {v}")

        return violation_count <= max_allowed_violations

    def identify_patterns(self, high_points: List[Tuple[int, float]], low_points: List[Tuple[int, float]],
                         df: pd.DataFrame, debug: bool = False) -> List[TrianglePattern]:
        """
        识别所有可能的三角形态
        使用归一化斜率进行判断
        """
        if len(high_points) < self.min_points or len(low_points) < self.min_points:
            return []

        patterns = []

        # 只使用最近的高点和低点（最后80%的数据范围）
        data_len = len(df)
        recent_threshold = int(data_len * 0.2)  # 从20%位置开始

        recent_high_points = [p for p in high_points if p[0] >= recent_threshold]
        recent_low_points = [p for p in low_points if p[0] >= recent_threshold]

        if len(recent_high_points) < self.min_points or len(recent_low_points) < self.min_points:
            # 如果最近的点不够，放宽到50%
            recent_threshold = int(data_len * 0.5)
            recent_high_points = [p for p in high_points if p[0] >= recent_threshold]
            recent_low_points = [p for p in low_points if p[0] >= recent_threshold]

        if len(recent_high_points) < self.min_points or len(recent_low_points) < self.min_points:
            return []

        # 先确定统一的形态范围（基于最近的高点和低点）
        pattern_start_idx = min(min(p[0] for p in recent_high_points), min(p[0] for p in recent_low_points))
        pattern_end_idx = max(max(p[0] for p in recent_high_points), max(p[0] for p in recent_low_points))

        if debug:
            print(f"    DEBUG: Pattern range [{pattern_start_idx}, {pattern_end_idx}], data_len {data_len}")
            print(f"    DEBUG: High points {len(recent_high_points)}, Low points {len(recent_low_points)}")

        # [修改] 使用新的外包络线算法拟合，传入统一的形态范围
        res_high = self.fit_upper_envelope(recent_high_points, df, pattern_start_idx, pattern_end_idx)
        res_low = self.fit_lower_envelope(recent_low_points, df, pattern_start_idx, pattern_end_idx)

        # 如果任一邊無法擬合出有效趨勢線（必須兩點一線、實體不破），則放棄此形態
        if res_high is None or res_low is None:
            if debug:
                print(f"    DEBUG: Fit failed - upper: {res_high is not None}, lower: {res_low is not None}")
            return []

        slope_high, intercept_high = res_high
        slope_low, intercept_low = res_low

        # 计算归一化斜率
        norm_slope_high = self.calculate_normalized_slope(high_points, slope_high)
        norm_slope_low = self.calculate_normalized_slope(low_points, slope_low)

        # 计算信心度
        high_confidence = self.calculate_confidence(high_points, slope_high, intercept_high, threshold=0.05)
        low_confidence = self.calculate_confidence(low_points, slope_low, intercept_low, threshold=0.05)

        if debug:
            print(f"    DEBUG: Norm slope - high: {norm_slope_high:.6f}, low: {norm_slope_low:.6f}")
            print(f"    DEBUG: Confidence - high: {high_confidence:.3f}, low: {low_confidence:.3f}")

        # 计算大小（使用最近的点）
        all_prices = [p[1] for p in recent_high_points + recent_low_points]
        if min(all_prices) > 0:
            size = (max(all_prices) - min(all_prices)) / min(all_prices)
        else:
            size = max(all_prices) - min(all_prices)

        # 使用已确定的形态范围
        start_idx = pattern_start_idx
        end_idx = pattern_end_idx

        # 整体信心度
        overall_confidence = (high_confidence + low_confidence) / 2

        # 归一化斜率的阈值(每个索引单位的百分比变化)
        # 0.001 means 0.1% change per index unit
        horizontal_threshold = 0.002  # 水平的阈值(放宽到0.2%)
        slope_threshold = 0.001       # 斜率的最小阈值(放宽到0.1%)

        if debug:
            print(f"    DEBUG: size={size:.2%}, overall_conf={overall_confidence:.3f}")

        # 上升三角形: 高点水平,低点上升
        if (abs(norm_slope_high) < horizontal_threshold and
            norm_slope_low > slope_threshold and
            overall_confidence > 0.2 and
            size >= self.min_size_threshold):

            # 验证K线实体是否都在通道内（延伸到最新数据）
            if self.validate_pattern_with_candle_bodies(df, start_idx, len(df) - 1,
                                                       slope_high, intercept_high,
                                                       slope_low, intercept_low, debug=debug):
                patterns.append(TrianglePattern(
                pattern_type=TriangleType.ASCENDING,
                start_idx=start_idx,
                end_idx=end_idx,
                high_points=high_points,
                low_points=low_points,
                confidence=overall_confidence,
                size=size,
                trendline_high=(slope_high, intercept_high),
                trendline_low=(slope_low, intercept_low),
                    normalized_slope_high=norm_slope_high,
                    normalized_slope_low=norm_slope_low
                ))

        # 下降三角形: 高点下降,低点水平
        if (norm_slope_high < -slope_threshold and
            abs(norm_slope_low) < horizontal_threshold and
            overall_confidence > 0.2 and
            size >= self.min_size_threshold):

            # 验证K线实体是否都在通道内（延伸到最新数据）
            if self.validate_pattern_with_candle_bodies(df, start_idx, len(df) - 1,
                                                       slope_high, intercept_high,
                                                       slope_low, intercept_low, debug=debug):
                patterns.append(TrianglePattern(
                pattern_type=TriangleType.DESCENDING,
                start_idx=start_idx,
                end_idx=end_idx,
                high_points=high_points,
                low_points=low_points,
                confidence=overall_confidence,
                size=size,
                trendline_high=(slope_high, intercept_high),
                trendline_low=(slope_low, intercept_low),
                    normalized_slope_high=norm_slope_high,
                    normalized_slope_low=norm_slope_low
                ))

        # 对称三角形: 高点下降,低点上升,且斜率相近
        slope_diff = abs(abs(norm_slope_high) - abs(norm_slope_low))
        if (norm_slope_high < -slope_threshold and
            norm_slope_low > slope_threshold and
            slope_diff < horizontal_threshold and
            overall_confidence > 0.2 and
            size >= self.min_size_threshold):

            # 验证K线实体是否都在通道内（延伸到最新数据）
            if self.validate_pattern_with_candle_bodies(df, start_idx, len(df) - 1,
                                                       slope_high, intercept_high,
                                                       slope_low, intercept_low, debug=debug):
                patterns.append(TrianglePattern(
                pattern_type=TriangleType.SYMMETRIC,
                start_idx=start_idx,
                end_idx=end_idx,
                high_points=high_points,
                low_points=low_points,
                confidence=overall_confidence,
                size=size,
                trendline_high=(slope_high, intercept_high),
                trendline_low=(slope_low, intercept_low),
                    normalized_slope_high=norm_slope_high,
                    normalized_slope_low=norm_slope_low
                ))

        # 水平震荡: 高点和低点都水平
        if (abs(norm_slope_high) < horizontal_threshold and
            abs(norm_slope_low) < horizontal_threshold and
            overall_confidence > 0.2 and
            size >= self.min_size_threshold):

            # 验证K线实体是否都在通道内（延伸到最新数据）
            if self.validate_pattern_with_candle_bodies(df, start_idx, len(df) - 1,
                                                       slope_high, intercept_high,
                                                       slope_low, intercept_low, debug=debug):
                patterns.append(TrianglePattern(
                pattern_type=TriangleType.CONSOLIDATION,
                start_idx=start_idx,
                end_idx=end_idx,
                high_points=high_points,
                low_points=low_points,
                confidence=overall_confidence,
                size=size,
                trendline_high=(slope_high, intercept_high),
                trendline_low=(slope_low, intercept_low),
                    normalized_slope_high=norm_slope_high,
                    normalized_slope_low=norm_slope_low
                ))

        # 上升通道: 高点和低点都上升,且斜率相近
        slope_diff_rising = abs(norm_slope_high - norm_slope_low)
        if (norm_slope_high > slope_threshold and
            norm_slope_low > slope_threshold and
            slope_diff_rising < horizontal_threshold and
            overall_confidence > 0.2 and
            size >= self.min_size_threshold):

            # 验证K线实体是否都在通道内（延伸到最新数据）
            if self.validate_pattern_with_candle_bodies(df, start_idx, len(df) - 1,
                                                       slope_high, intercept_high,
                                                       slope_low, intercept_low, debug=debug):
                patterns.append(TrianglePattern(
                pattern_type=TriangleType.RISING_CHANNEL,
                start_idx=start_idx,
                end_idx=end_idx,
                high_points=high_points,
                low_points=low_points,
                confidence=overall_confidence,
                size=size,
                trendline_high=(slope_high, intercept_high),
                trendline_low=(slope_low, intercept_low),
                    normalized_slope_high=norm_slope_high,
                    normalized_slope_low=norm_slope_low
                ))

        # 下降通道: 高点和低点都下降,且斜率相近
        slope_diff_falling = abs(norm_slope_high - norm_slope_low)
        if (norm_slope_high < -slope_threshold and
            norm_slope_low < -slope_threshold and
            slope_diff_falling < horizontal_threshold and
            overall_confidence > 0.2 and
            size >= self.min_size_threshold):

            # 验证K线实体是否都在通道内（延伸到最新数据）
            if self.validate_pattern_with_candle_bodies(df, start_idx, len(df) - 1,
                                                       slope_high, intercept_high,
                                                       slope_low, intercept_low):
                patterns.append(TrianglePattern(
                pattern_type=TriangleType.FALLING_CHANNEL,
                start_idx=start_idx,
                end_idx=end_idx,
                high_points=high_points,
                low_points=low_points,
                confidence=overall_confidence,
                size=size,
                trendline_high=(slope_high, intercept_high),
                trendline_low=(slope_low, intercept_low),
                    normalized_slope_high=norm_slope_high,
                    normalized_slope_low=norm_slope_low
                ))

        return patterns

    def find_patterns(self, df: pd.DataFrame, window: int = 10, debug: bool = False) -> List[TrianglePattern]:
        """寻找所有三角形态"""
        if df is None or df.empty or len(df) < 20:
            return []

        high_points, low_points = self.find_high_low_points(df, window)

        if len(high_points) < self.min_points or len(low_points) < self.min_points:
            if debug:
                print(f"    DEBUG: high={len(high_points)}, low={len(low_points)} (need>={self.min_points})")
            return []

        return self.identify_patterns(high_points, low_points, df, debug=debug)

    def find_best_pattern(self, df: pd.DataFrame, window: int = 10, require_recent: bool = True) -> Optional[TrianglePattern]:
        """
        找到最佳形态

        Args:
            df: K线数据
            window: 窗口大小
            require_recent: 是否要求形态必须包含最近的数据点（默认True）
        """
        patterns = self.find_patterns(df, window)

        if not patterns:
            return None

        # 如果要求形态必须是最近的，过滤掉过时的形态
        if require_recent:
            data_len = len(df)
            recent_threshold = data_len * 0.8  # 形态结束点必须在最后20%的数据范围内

            recent_patterns = [p for p in patterns if p.end_idx >= recent_threshold]

            if not recent_patterns:
                # 如果没有最近的形态，放宽到50%
                recent_threshold = data_len * 0.5
                recent_patterns = [p for p in patterns if p.end_idx >= recent_threshold]

            if recent_patterns:
                patterns = recent_patterns

        # 根据大小和信心度排序
        def pattern_score(pattern: TrianglePattern) -> float:
            return pattern.size * pattern.confidence

        return max(patterns, key=pattern_score)

    def visualize_pattern(self, df: pd.DataFrame, pattern: TrianglePattern, title: str = "Pattern Analysis") -> plt.Figure:
        """可视化形态"""
        fig, ax = plt.subplots(figsize=(14, 8))

        # 绘制价格线
        x = np.arange(len(df))
        ax.plot(x, df['Close'], label='Close Price', color='black', alpha=0.7, linewidth=0.8)

        # 标示高点
        if pattern.high_points:
            high_indices = [p[0] for p in pattern.high_points]
            high_prices = [p[1] for p in pattern.high_points]
            ax.scatter(high_indices, high_prices, color='red', s=60, label='High Points', zorder=5)

        # 标示低点
        if pattern.low_points:
            low_indices = [p[0] for p in pattern.low_points]
            low_prices = [p[1] for p in pattern.low_points]
            ax.scatter(low_indices, low_prices, color='green', s=60, label='Low Points', zorder=5)

        # 绘制趋势线
        x_range = np.array([pattern.start_idx, pattern.end_idx])
        y_high = pattern.trendline_high[0] * x_range + pattern.trendline_high[1]
        ax.plot(x_range, y_high, color='red', linestyle='--', label='High Trend', alpha=0.8, linewidth=2)

        y_low = pattern.trendline_low[0] * x_range + pattern.trendline_low[1]
        ax.plot(x_range, y_low, color='green', linestyle='--', label='Low Trend', alpha=0.8, linewidth=2)

        # 标示区间
        ax.axvspan(pattern.start_idx, pattern.end_idx, alpha=0.1, color='yellow', label='Pattern Zone')

        ax.set_title(f'{title}\n{pattern.pattern_type.value.title()} Triangle | '
                    f'Confidence: {pattern.confidence:.2f} | Size: {pattern.size:.2%} | '
                    f'Norm Slopes: High={pattern.normalized_slope_high:.4f}, Low={pattern.normalized_slope_low:.4f}')
        ax.set_xlabel('Time Index')
        ax.set_ylabel('Price')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig


# 测试代码
if __name__ == "__main__":
    import sys
    import os

    # 设置UTF-8编码
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from data.data_fetcher import get_data_fetcher

    print("改进的形态分析器测试")
    print("=" * 70)

    # 测试多个币种
    symbols = ["BTC-USDT", "ETH-USDT", "PI-USDT"]

    for symbol in symbols:
        print(f"\n分析: {symbol}")
        print("-" * 70)

        try:
            fetcher = get_data_fetcher("okx")
            df = fetcher.get_historical_klines(symbol, "1d", limit=100)

            if df is None or df.empty:
                print(f"  无法获取数据")
                continue

            analyzer = ImprovedPatternAnalyzer(min_size_threshold=0.02, min_points=3)

            # 测试不同窗口
            best_overall = None
            best_score = 0

            for window in [5, 8, 10]:
                patterns = analyzer.find_patterns(df, window=window, debug=True)

                if patterns:
                    print(f"\n  窗口{window}: 发现 {len(patterns)} 个形态")
                    for p in patterns:
                        score = p.size * p.confidence
                        print(f"    - {p.pattern_type.value}: "
                              f"信心度={p.confidence:.2f}, 大小={p.size:.2%}, "
                              f"归一化斜率(高/低)={p.normalized_slope_high:.4f}/{p.normalized_slope_low:.4f}")

                        if score > best_score:
                            best_score = score
                            best_overall = p

            if best_overall:
                print(f"\n  ✓ 最佳形态: {best_overall.pattern_type.value}")
                fig = analyzer.visualize_pattern(df, best_overall, title=symbol)
                plt.savefig(f"enhanced_{symbol.replace('-', '_')}_patterns.png", dpi=150, bbox_inches='tight')
                print(f"  图表已保存")
                plt.close()
            else:
                print(f"\n  未检测到形态")

        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("测试完成!")
