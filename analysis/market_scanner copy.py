# -*- coding: utf-8 -*-
"""
Market Scanner - Improved Version: Only find patterns where price is currently in channel
Key changes:
1. Requires 3+ points
2. Current price must be within channel range
3. Prioritize patterns with maximum span
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

print("Initializing Improved Pattern Scanner (In-Channel Only)...", flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from data.data_fetcher import get_data_fetcher


class MathematicalPatternValidator:
    """Mathematical Pattern Validator"""

    @staticmethod
    def calculate_slope_angle(slope):
        """Calculate the angle corresponding to the slope (in degrees)"""
        return np.degrees(np.arctan(slope))

    @staticmethod
    def calculate_intersection_point(resistance, support):
        """Calculate the intersection point of two lines"""
        slope1 = resistance['slope']
        intercept1 = resistance['intercept']
        slope2 = support['slope']
        intercept2 = support['intercept']

        current_idx = min(resistance['valid_end'], support['valid_end'])
        slope_diff = abs(slope1 - slope2)

        if (slope1 > 0 and slope2 < 0) or (slope1 < 0 and slope2 > 0):
            if slope_diff < 1e-10:
                return float('inf'), 'diverging'
            x_intersect = (intercept2 - intercept1) / (slope1 - slope2)
            distance_from_current = current_idx - x_intersect
            return distance_from_current, 'diverging'

        if slope_diff < 1e-10:
            return float('inf'), 'parallel'

        x_intersect = (intercept2 - intercept1) / (slope1 - slope2)
        distance_from_current = x_intersect - current_idx

        if distance_from_current > 500 or distance_from_current < -500:
            return distance_from_current, 'parallel'
        elif distance_from_current > 0:
            return distance_from_current, 'converging'
        else:
            return distance_from_current, 'diverging_past'

    @staticmethod
    def calculate_r_squared(points, slope, intercept):
        """Calculate R-squared (coefficient of determination)"""
        if len(points) < 2:
            return 0.0

        y_actual = np.array([p['price'] for p in points])
        y_predicted = np.array([slope * p['index'] + intercept for p in points])
        y_mean = np.mean(y_actual)

        ss_tot = np.sum((y_actual - y_mean) ** 2)
        ss_res = np.sum((y_actual - y_predicted) ** 2)

        if ss_tot < 1e-10:
            if ss_res < 1e-10:
                return 1.0
            else:
                return 0.0

        r_squared = 1 - (ss_res / ss_tot)
        return max(0.0, min(1.0, r_squared))

    @staticmethod
    def calculate_parallelism_score(upper_slope, lower_slope):
        """Calculate parallelism score (0-1)"""
        if abs(upper_slope) < 1e-6 and abs(lower_slope) < 1e-6:
            return 1.0

        angle1 = np.degrees(np.arctan(upper_slope))
        angle2 = np.degrees(np.arctan(lower_slope))
        angle_diff = abs(angle1 - angle2)

        parallelism = max(0, 1 - (angle_diff / 45))
        return parallelism

    @staticmethod
    def calculate_width_consistency(resistance, support, num_samples=10):
        """Calculate channel width consistency (0-1)"""
        first_idx = min(resistance['first_idx'], support['first_idx'])
        last_idx = min(resistance['valid_end'], support['valid_end'])

        if last_idx - first_idx < 10:
            return 0.0

        sample_indices = np.linspace(first_idx, last_idx, num_samples, dtype=int)
        widths = []

        for idx in sample_indices:
            upper_price = resistance['slope'] * idx + resistance['intercept']
            lower_price = support['slope'] * idx + support['intercept']
            width = abs(upper_price - lower_price)
            widths.append(width)

        mean_width = np.mean(widths)
        std_width = np.std(widths)

        if mean_width == 0:
            return 0.0

        cv = std_width / mean_width
        consistency = max(0, 1 - (cv / 0.3))
        return consistency


class RobustPatternClassifier:
    """Robust Pattern Classifier"""

    def __init__(self):
        self.validator = MathematicalPatternValidator()

    def identify_divergence_apex(self, resistance, support):
        """Identify the apex (turning point) of the divergence pattern"""
        intersection_x, _ = self.validator.calculate_intersection_point(
            resistance, support
        )

        apex_price = resistance['slope'] * intersection_x + resistance['intercept']
        current_idx = min(resistance['valid_end'], support['valid_end'])
        distance_from_current = intersection_x - current_idx

        return {
            'apex_index': intersection_x,
            'apex_price': apex_price,
            'distance_from_current': distance_from_current,
            'is_in_past': distance_from_current < 0,
            'type': 'divergence_apex'
        }

    def classify(self, resistance, support):
        """Multi-validation pattern classification"""
        if not resistance or not support:
            return "Unknown Pattern", 0.0, {}

        upper_slope = resistance['slope']
        lower_slope = support['slope']

        current_idx = min(resistance['valid_end'], support['valid_end'])
        first_idx = min(resistance['first_idx'], support['first_idx'])
        span = current_idx - first_idx

        if span < 20:
            return "Insufficient Span", 0.0, {}

        start_upper = upper_slope * first_idx + resistance['intercept']
        start_lower = lower_slope * first_idx + support['intercept']
        start_width = abs(start_upper - start_lower)

        end_upper = upper_slope * current_idx + resistance['intercept']
        end_lower = lower_slope * current_idx + support['intercept']
        end_width = abs(end_upper - end_lower)

        width_ratio = end_width / start_width if start_width > 0 else 1.0

        upper_r2 = self.validator.calculate_r_squared(
            resistance['points'], upper_slope, resistance['intercept']
        )
        lower_r2 = self.validator.calculate_r_squared(
            support['points'], lower_slope, support['intercept']
        )

        parallelism = self.validator.calculate_parallelism_score(upper_slope, lower_slope)
        width_consistency = self.validator.calculate_width_consistency(resistance, support)

        upper_angle = self.validator.calculate_slope_angle(upper_slope)
        lower_angle = self.validator.calculate_slope_angle(lower_slope)

        intersection_distance, intersection_type = self.validator.calculate_intersection_point(
            resistance, support
        )

        metrics = {
            'upper_r2': upper_r2,
            'lower_r2': lower_r2,
            'parallelism': parallelism,
            'width_consistency': width_consistency,
            'upper_angle': upper_angle,
            'lower_angle': lower_angle,
            'width_ratio': width_ratio,
            'span': span,
            'upper_points': resistance['count'],
            'lower_points': support['count'],
            'intersection_distance': intersection_distance,
            'intersection_type': intersection_type
        }

        upper_r2_weight = max(0.1, upper_r2)
        lower_r2_weight = max(0.1, lower_r2)

        base_confidence = (
            (upper_r2_weight * 0.3) +
            (lower_r2_weight * 0.3) +
            (min(resistance['count'], 10) / 10 * 0.2) +
            (min(support['count'], 10) / 10 * 0.2)
        )

        if intersection_type in ['diverging', 'diverging_past']:
            divergence_strength = abs(upper_angle) + abs(lower_angle)
            apex_info = self.identify_divergence_apex(resistance, support)
            metrics['apex'] = apex_info

            r2_penalty = 1.0
            if upper_r2 < 0.5 or lower_r2 < 0.5:
                r2_penalty = 0.7

            confidence = (base_confidence * 0.7 + (min(divergence_strength / 30, 1) * 0.3)) * r2_penalty

            if divergence_strength > 15:
                return "Expanding Divergence", confidence, metrics
            else:
                return "Diverging Megaphone", confidence, metrics

        if intersection_type == 'parallel':
            both_horizontal = abs(upper_angle) < 5 and abs(lower_angle) < 5

            if both_horizontal:
                confidence = (
                    base_confidence * 0.5 +
                    parallelism * 0.25 +
                    width_consistency * 0.25
                )
                return "Rectangle Channel", confidence, metrics
            elif upper_slope > 0 and lower_slope > 0:
                confidence = base_confidence * 0.6 + parallelism * 0.2 + width_consistency * 0.2
                return "Ascending Channel", confidence, metrics
            elif upper_slope < 0 and lower_slope < 0:
                confidence = base_confidence * 0.6 + parallelism * 0.2 + width_consistency * 0.2
                return "Descending Channel", confidence, metrics
            else:
                confidence = base_confidence * 0.5
                return "Complex Channel", confidence, metrics

        if intersection_type == 'converging':
            convergence_rate = 1 - width_ratio

            if intersection_distance < 100:
                distance_confidence = 0.9
            elif intersection_distance < 300:
                distance_confidence = 0.7
            else:
                distance_confidence = 0.5

            confidence = (
                base_confidence * 0.5 +
                convergence_rate * 0.3 +
                distance_confidence * 0.2
            )

            if upper_slope > 0 and lower_slope > 0:
                return "Ascending Wedge (Converging)", confidence, metrics
            elif upper_slope < 0 and lower_slope < 0:
                return "Descending Wedge (Converging)", confidence, metrics
            else:
                return "Symmetric Convergence", confidence, metrics

        if width_ratio > 1.15:
            confidence = base_confidence * 0.5
            return "Irregular Expansion", confidence, metrics
        elif width_ratio < 0.85:
            confidence = base_confidence * 0.5
            return "Irregular Convergence", confidence, metrics
        else:
            confidence = base_confidence * 0.4
            return "Complex Pattern", confidence, metrics


class ExhaustiveTrendlineDetector:
    """Trendline Detector - Improved Version"""

    def __init__(self, order=8, tolerance=0.006, min_points=3):
        self.order = order
        self.tolerance = tolerance
        self.min_points = min_points  # Minimum points required
        self.classifier = RobustPatternClassifier()
        self.validator = MathematicalPatternValidator()

    def check_no_body_penetration(self, df, p1, p2, line_type='resistance'):
        """Check if there is any candle body penetrating between two points"""
        idx1, price1 = p1['index'], p1['price']
        idx2, price2 = p2['index'], p2['price']

        if idx2 == idx1:
            return False

        slope = (price2 - price1) / (idx2 - idx1)
        intercept = price1 - slope * idx1

        start = min(idx1, idx2)
        end = max(idx1, idx2)

        for i in range(start, end + 1):
            line_price = slope * i + intercept
            candle = df.iloc[i]

            if line_type == 'resistance':
                body_top = max(candle['Open'], candle['Close'])
                if body_top > line_price:
                    return False
            else:
                body_bottom = min(candle['Open'], candle['Close'])
                if body_bottom < line_price:
                    return False

        return True

    def is_point_on_line(self, point, slope, intercept):
        """Check if point is on the line (within tolerance)"""
        expected_price = slope * point['index'] + intercept
        error = abs(point['price'] - expected_price) / point['price']
        return error < self.tolerance

    def find_all_points_on_line(self, pivots, slope, intercept):
        """Find all points on this line"""
        points_on_line = []
        for p in pivots:
            if self.is_point_on_line(p, slope, intercept):
                points_on_line.append(p)
        return points_on_line

    def check_line_validity_to_current(self, df, slope, intercept, start_idx, line_type='resistance'):
        """Check from start_idx to the last candle, whether there are no bodies penetrating"""
        end_idx = len(df) - 1

        for i in range(start_idx, end_idx + 1):
            line_price = slope * i + intercept
            candle = df.iloc[i]

            if line_type == 'resistance':
                body_top = max(candle['Open'], candle['Close'])
                if body_top > line_price:
                    return False, i
            else:
                body_bottom = min(candle['Open'], candle['Close'])
                if body_bottom < line_price:
                    return False, i

        return True, end_idx

    def is_price_in_channel(self, df, resistance, support):
        """
        Check if current price is within the channel
        """
        if not resistance or not support:
            return False

        current_idx = len(df) - 1
        current_price = df.iloc[current_idx]['Close']

        # Calculate channel upper and lower bounds at current position
        upper_price = resistance['slope'] * current_idx + resistance['intercept']
        lower_price = support['slope'] * current_idx + support['intercept']

        # Allow 3% margin
        channel_height = abs(upper_price - lower_price)
        margin = channel_height * 0.03

        # Check if price is within channel
        in_channel = (lower_price - margin) <= current_price <= (upper_price + margin)

        return in_channel

    def detect_patterns(self, df):
        """Detect resistance and support lines"""
        swing_highs = self.find_pivot_highs(df)
        swing_lows = self.find_pivot_lows(df)

        resistance = self.exhaustive_search_trendline(df, swing_highs, 'resistance')
        support = self.exhaustive_search_trendline(df, swing_lows, 'support')

        if not resistance or not support:
            return None, None, "No Channel", 0.0, {}

        # Force check: current price must be within channel
        if not self.is_price_in_channel(df, resistance, support):
            return None, None, "Price Outside Channel", 0.0, {}

        # Use robust classifier for classification
        pattern_name, confidence, metrics = self.classifier.classify(resistance, support)

        # Add channel status to metrics
        current_idx = len(df) - 1
        current_price = df.iloc[current_idx]['Close']
        upper_price = resistance['slope'] * current_idx + resistance['intercept']
        lower_price = support['slope'] * current_idx + support['intercept']

        metrics['current_price'] = current_price
        metrics['upper_boundary'] = upper_price
        metrics['lower_boundary'] = lower_price

        return resistance, support, pattern_name, confidence, metrics

    def find_pivot_lows(self, df):
        """Find all pivot lows, sort by price and assign priority"""
        lows = df['Low'].values
        valley_indices = argrelextrema(lows, np.less, order=self.order)[0]

        pivots = []
        for idx in valley_indices:
            if idx < len(df):
                pivots.append({
                    'index': int(idx),
                    'price': float(lows[idx])
                })

        if pivots:
            pivots_sorted_by_price = sorted(pivots, key=lambda x: x['price'])

            for i, pivot in enumerate(pivots_sorted_by_price):
                pivot['priority'] = len(pivots_sorted_by_price) - i

        return sorted(pivots, key=lambda x: x['index'])

    def find_pivot_highs(self, df):
        """Find all pivot highs, sort by price and assign priority"""
        highs = df['High'].values
        peak_indices = argrelextrema(highs, np.greater, order=self.order)[0]

        pivots = []
        for idx in peak_indices:
            if idx < len(df):
                pivots.append({
                    'index': int(idx),
                    'price': float(highs[idx])
                })

        if pivots:
            pivots_sorted_by_price = sorted(pivots, key=lambda x: x['price'], reverse=True)

            for i, pivot in enumerate(pivots_sorted_by_price):
                pivot['priority'] = len(pivots_sorted_by_price) - i

        return sorted(pivots, key=lambda x: x['index'])

    def exhaustive_search_trendline(self, df, pivots, line_type='resistance'):
        """
        Prioritize patterns with maximum span
        """
        if len(pivots) < self.min_points:  # Use min_points parameter
            return None

        valid_lines = []
        current_idx = len(df) - 1
        latest_pivot_idx = max(p['index'] for p in pivots) if pivots else 0

        def priority_score(p):
            base_priority = p.get('priority', 0)
            recency_bonus = (p['index'] / current_idx) * 10
            return base_priority + recency_bonus

        pivots_by_priority = sorted(pivots, key=priority_score, reverse=True)

        max_priority_points = min(15, len(pivots_by_priority))

        for i, p1 in enumerate(pivots_by_priority[:max_priority_points]):
            for j in range(i + 1, len(pivots_by_priority)):
                p2 = pivots_by_priority[j]

                if not self.check_no_body_penetration(df, p1, p2, line_type):
                    continue

                slope = (p2['price'] - p1['price']) / (p2['index'] - p1['index'])
                intercept = p1['price'] - slope * p1['index']

                points_on_line = self.find_all_points_on_line(pivots, slope, intercept)

                # Require at least min_points
                if len(points_on_line) < self.min_points:
                    continue

                r_squared = self.validator.calculate_r_squared(points_on_line, slope, intercept)

                # Relax R2 requirement but require more points
                if r_squared < 0.4 and len(points_on_line) < 4:
                    continue

                first_idx = min(p['index'] for p in points_on_line)
                is_valid, valid_end = self.check_line_validity_to_current(
                    df, slope, intercept, first_idx, line_type
                )

                if not is_valid:
                    continue

                last_idx = max(p['index'] for p in points_on_line)
                span = last_idx - first_idx
                has_latest = (last_idx == latest_pivot_idx)
                recency = current_idx - last_idx

                extension_ratio = (valid_end - last_idx) / (len(df) - last_idx) if len(df) - last_idx > 0 else 0

                # Weight span more heavily to find largest patterns
                quality_score = (
                    r_squared * 0.3 +  # Lower R2 weight
                    min(len(points_on_line) / 10, 1.0) * 0.3 +
                    min(span / 150, 1.0) * 0.3 +  # Higher span weight
                    extension_ratio * 0.1
                )

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
                    'recency': recency,
                    'r_squared': r_squared,
                    'quality_score': quality_score
                })

        if not valid_lines:
            return None

        # Sort priority: span > quality score > point count
        valid_lines.sort(key=lambda x: (
            x['span'],           # Primary: maximum span
            x['quality_score'],  # Secondary: quality score
            x['count'],          # Tertiary: point count
            x['has_latest']
        ), reverse=True)

        return valid_lines[0]


class ChartDrawer:
    """Chart Drawer"""

    def draw_pattern_chart(self, df, resistance, support, pattern_name, confidence, metrics,
                          symbol, timeframe, save_path):
        """Draw trendline chart"""
        fig, ax = plt.subplots(figsize=(20, 11))

        start_idx = len(df) - 200

        if resistance:
            start_idx = min(start_idx, resistance['first_idx'] - 10)
        if support:
            start_idx = min(start_idx, support['first_idx'] - 10)

        start_idx = max(0, start_idx)

        # Draw candlesticks
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            color = '#EF5350' if row['Close'] >= row['Open'] else '#26A69A'

            ax.plot([i, i], [row['Low'], row['High']],
                   color=color, linewidth=1.2, alpha=0.7)

            body_h = abs(row['Close'] - row['Open'])
            body_b = min(row['Open'], row['Close'])
            rect = Rectangle((i - 0.4, body_b), 0.8, body_h,
                           facecolor=color, edgecolor=color, alpha=0.9)
            ax.add_patch(rect)

        # Draw trendlines
        def draw_trendline(line, color, label):
            if not line:
                return

            draw_start = line['first_idx']
            draw_end = line['valid_end']

            if line['is_active']:
                display_end = draw_end + 10
            else:
                display_end = draw_end

            x = [draw_start, display_end]
            y = [line['slope'] * xi + line['intercept'] for xi in x]

            style = '-' if line['is_active'] else '--'
            ax.plot(x, y, color=color, linestyle=style, linewidth=3,
                   alpha=0.9, label=f"{label} ({line['count']}pts, span:{line['span']})")

            for p in line['points']:
                priority = p.get('priority', 0)
                max_priority = max([pt.get('priority', 0) for pt in line['points']], default=1)
                if max_priority > 0:
                    size_scale = 0.7 + (priority / max_priority) * 0.6
                else:
                    size_scale = 1.0

                marker_size = 10 * size_scale
                edge_width = 2.5 * size_scale

                ax.plot(p['index'], p['price'], 'o', color=color,
                       markersize=marker_size, markeredgewidth=edge_width,
                       markeredgecolor='white', zorder=5)

            if not line['is_active']:
                ax.axvline(x=draw_end + 1, color=color,
                          linestyle=':', linewidth=2, alpha=0.7)

            end_price = line['slope'] * display_end + line['intercept']
            ax.text(display_end + 2, end_price, f"{end_price:.2f}",
                   color=color, fontweight='bold', fontsize=12,
                   va='center', ha='left',
                   bbox=dict(boxstyle='round,pad=0.5',
                   facecolor='white', edgecolor=color, linewidth=2, alpha=0.95))

        if resistance:
            draw_trendline(resistance, '#D32F2F', 'Resistance')
        if support:
            draw_trendline(support, '#388E3C', 'Support')

        # Draw center dashed line between resistance and support
        if resistance and support:
            center_draw_start = min(resistance['first_idx'], support['first_idx'])
            center_draw_end = min(resistance['valid_end'], support['valid_end'])
            if resistance['is_active'] or support['is_active']:
                center_draw_end = center_draw_end + 10

            center_x = [center_draw_start, center_draw_end]
            center_y = []
            for xi in center_x:
                upper_y = resistance['slope'] * xi + resistance['intercept']
                lower_y = support['slope'] * xi + support['intercept']
                center_y.append((upper_y + lower_y) / 2)

            ax.plot(center_x, center_y, color='#9E9E9E', linestyle='--', linewidth=2,
                   alpha=0.7, label='Channel Center')

        # Mark current price
        if metrics and 'current_price' in metrics:
            current_idx = len(df) - 1
            current_price = metrics['current_price']

            # Mark current position point
            ax.plot(current_idx, current_price, 'D', color='#FF9800',
                   markersize=12, markeredgecolor='white', markeredgewidth=2, zorder=10,
                   label=f'Current Price: ${current_price:.4f}')

        # Status info
        status = []
        if resistance:
            st = 'Active' if resistance['is_active'] else 'Broken'
            status.append(f"R:{st}({resistance['count']}pts)")
        else:
            status.append("R:None")

        if support:
            st = 'Active' if support['is_active'] else 'Broken'
            status.append(f"S:{st}({support['count']}pts)")
        else:
            status.append("S:None")

        conf_str = f"{confidence:.0%}" if confidence > 0 else "N/A"

        quality_indicators = []
        if metrics:
            if 'upper_r2' in metrics:
                quality_indicators.append(f"R²:{metrics['upper_r2']:.2f}/{metrics['lower_r2']:.2f}")

            if 'parallelism' in metrics:
                quality_indicators.append(f"Parallelism:{metrics['parallelism']:.0%}")

        quality_str = " | ".join(quality_indicators) if quality_indicators else ""

        title = f"{symbol} | {timeframe} | {pattern_name} ({conf_str}) | {' | '.join(status)}"
        if quality_str:
            title += f"\n{quality_str}"

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        ax.set_xlabel('Candle Index', fontsize=12)
        ax.set_ylabel('Price', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)

        # Add all elements to the legend
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, loc='upper left', fontsize=11, framealpha=0.95)

        ax.set_xlim(start_idx - 5, len(df) + 15)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)


class MarketScanner:
    """Market Scanner - Improved Version"""

    def __init__(self, lookback=800, min_points=3):
        self.lookback = lookback
        self.detector = ExhaustiveTrendlineDetector(order=8, tolerance=0.006, min_points=min_points)
        self.drawer = ChartDrawer()
        self.fetcher = get_data_fetcher("okx")

    def scan(self, symbols, timeframes=["15m", "1h", "4h"]):
        """Scan the market"""
        print(f"\n{'='*80}")
        print(f"  Improved Pattern Scanner (In-Channel Only)")
        print(f"  Conditions: >={self.detector.min_points} points + Price in channel + Max span priority")
        print(f"  Lookback: {self.lookback} candles")
        print(f"{'='*80}\n")

        os.makedirs("pattern_charts", exist_ok=True)

        results_summary = []

        for symbol in symbols:
            print(f"\n{'-'*80}")
            print(f"[SCAN] {symbol}")
            print(f"{'-'*80}")

            for timeframe in timeframes:
                try:
                    df = self.fetcher.get_historical_klines(symbol, timeframe, self.lookback)

                    if df is None or len(df) < 100:
                        print(f"  [{timeframe}] [!] Insufficient Data")
                        continue

                    resistance, support, pattern_name, confidence, metrics = \
                        self.detector.detect_patterns(df)

                    # Only display if valid pattern found
                    if resistance and support:
                        result = []

                        status = "+" if resistance['is_active'] else "-"
                        result.append(f"R:{status}({resistance['count']}pts,span:{resistance['span']})")

                        status = "+" if support['is_active'] else "-"
                        result.append(f"S:{status}({support['count']}pts,span:{support['span']})")

                        conf_str = f"{confidence:.0%}"

                        quality_str = ""
                        if metrics and 'upper_r2' in metrics:
                            r2_upper = metrics['upper_r2']
                            r2_lower = metrics['lower_r2']

                            quality_str = f"R²:{r2_upper:.2f}/{r2_lower:.2f}"

                        output = f"  [{timeframe}] [OK] {' | '.join(result)} | {pattern_name} ({conf_str})"
                        if quality_str:
                            output += f" | {quality_str}"

                        print(output)

                        # Save results
                        results_summary.append({
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'pattern': pattern_name,
                            'confidence': confidence,
                            'span': max(resistance['span'], support['span'])
                        })

                        save_path = f"pattern_charts/{symbol.replace('-', '_')}_{timeframe}_inchannel.png"
                        self.drawer.draw_pattern_chart(df, resistance, support,
                                                       pattern_name, confidence, metrics,
                                                       symbol, timeframe, save_path)
                    else:
                        # Not found or outside channel
                        reason = pattern_name if pattern_name in ["No Channel", "Price Outside Channel"] else "No Valid Pattern"
                        print(f"  [{timeframe}] [--] {reason}")

                except Exception as e:
                    print(f"  [{timeframe}] [X] Error: {str(e)}")
                    import traceback
                    traceback.print_exc()

        print(f"\n{'='*80}")
        print(f"  Scan Complete!")
        print(f"  Found {len(results_summary)} valid patterns (current price in channel)")
        print(f"{'='*80}\n")

        # Display summary
        if results_summary:
            print("\n[Summary] Patterns sorted by span:")
            results_summary.sort(key=lambda x: x['span'], reverse=True)
            for r in results_summary:
                print(f"  {r['symbol']} [{r['timeframe']}] - {r['pattern']} (span:{r['span']}, conf:{r['confidence']:.0%})")


if __name__ == "__main__":
    targets = ["BTC-USDT", "ETH-USDT"]

    # Parameters:
    # lookback: how many candles to look back
    # min_points: minimum points for a valid trendline (default 3)
    scanner = MarketScanner(lookback=500, min_points=5)

    scanner.scan(targets, timeframes=["15m", "1h", "4h", "1d"])