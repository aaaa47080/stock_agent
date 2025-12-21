# 形态检测模块说明

本目录包含3个核心的形态检测程序，用于自动识别K线图中的技术形态。

## 📁 核心文件

### 1. `improved_pattern_analyzer.py` (19KB)
**形态分析引擎 - 核心算法**

功能：
- 自动检测6种技术形态：
  - 上升三角形（看涨）
  - 下降三角形（看跌）
  - 对称三角形（中性）
  - 水平震荡区间（中性）
  - 上升通道（看涨）
  - 下降通道（看跌）
- 使用归一化斜率算法，适应不同价格范围
- 自动过滤历史过期形态，只保留最新有效的形态
- 计算形态信心度和大小

主要类：
- `ImprovedPatternAnalyzer` - 形态分析器
- `TrianglePattern` - 形态数据结构
- `TriangleType` - 形态类型枚举

### 2. `candlestick_pattern_visualizer.py` (14KB)
**K线图可视化工具 - 生成图表**

功能：
- 绘制真正的K线图（蜡烛图）
- 高点/低点标注在K线的实际High/Low位置
- 趋势线自动延伸到最新价格
- 自动检测突破（向上/向下/仍在通道内）
- 生成带完整信息的PNG图表

使用方法：
```bash
python analysis/candlestick_pattern_visualizer.py
```

生成的图表包含：
- 红色/绿色K线（涨/跌）
- 高点趋势线（红色虚线）
- 低点趋势线（绿色虚线）
- 当前价格标记
- 突破状态提示

### 3. `pattern_detector_integration.py` (8.3KB)
**整合接口 - 供主分析流程调用**

功能：
- 提供简单的API接口
- 将形态检测结果格式化为标准JSON
- 生成交易信号建议
- 适合整合到主分析系统

主要函数：
- `analyze_patterns_for_symbol(df, symbol)` - 分析单个币种
- `get_pattern_trading_signal(pattern_result)` - 获取交易信号
- `format_pattern_result(pattern)` - 格式化结果

### 4. `market_scanner.py`
**簡單通道掃描器 - 快速市場掃描**

功能：
- 快速掃描多個交易對（如 BTC, ETH, SOL）的通道形態
- 基於 Pivot Point（高低轉折點）連接算法
- **智能過濾機制**：
  - **時效性**：只顯示目前依然有效，或在最近 2 根 K 線內剛突破的通道
  - **權威性**：優先顯示由更多轉折點（Pivot Points）組成的趨勢線
- **視覺化優化**：
  - 自動標記通道突破點（Breakout Point）
  - 通道線只畫到突破位置，不誤導性延伸
  - 動態調整繪圖範圍，確保完整顯示通道歷史
- 終端機輸出簡潔，只顯示有效通道的摘要

使用方法：
```bash
python analysis/market_scanner.py
```

生成的圖表位於 `pattern_charts/` 目錄下：
- `*_channel.png`：包含通道線、轉折點標記和突破點標記

## 🎯 使用示例

### 快速生成图表
```bash
python analysis/candlestick_pattern_visualizer.py
```

### 在代码中使用
```python
from analysis.pattern_detector_integration import analyze_patterns_for_symbol, get_pattern_trading_signal
from data.data_fetcher import get_data_fetcher

# 获取K线数据
fetcher = get_data_fetcher("okx")
df = fetcher.get_historical_klines("BTC-USDT", "1d", limit=100)

# 分析形态
result = analyze_patterns_for_symbol(df, "BTC-USDT")

if result.get("has_pattern"):
    print(f"检测到: {result['pattern_name']}")
    print(f"信心度: {result['confidence']}")

    # 获取交易信号
    signal = get_pattern_trading_signal(result)
    print(f"信号: {signal['signal']} (强度: {signal['strength']})")
```

## 📊 输出示例

当前目录下的3张图表展示了实际检测效果：
- `candlestick_BTC_USDT_falling_channel.png` - BTC下降通道（价格仍在通道内）
- `candlestick_ETH_USDT_falling_channel.png` - ETH下降通道（价格仍在通道内）
- `candlestick_SOL_USDT_falling_channel.png` - SOL下降通道（已向上突破）

## 🔧 技术特点

1. **归一化斜率** - 使用价格百分比变化率，不受价格绝对值影响
2. **时效性过滤** - 只保留延伸到最近20%数据的形态
3. **突破检测** - 自动判断当前价格是否突破通道
4. **趋势线延伸** - 趋势线延伸到最新K线，实时显示通道位置
5. **多窗口扫描** - 自动尝试不同窗口大小，找到最佳形态

## 📝 注意事项

- 需要至少20条K线数据才能进行形态检测
- 形态的可靠性与信心度和大小相关
- 突破通道可能是假突破，需结合其他指标确认
- 图表仅供参考，不构成投资建议

## 🚀 下一步

如果图表效果满意，可以将 `pattern_detector_integration.py` 整合到主分析流程 `interfaces/chat_interface.py` 的 `_fetch_shared_data()` 方法中。
