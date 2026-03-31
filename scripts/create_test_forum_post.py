#!/usr/bin/env python
"""
創建論壇測試文章
"""
import sys
import os

# Add project root to path (parent of scripts directory)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.database.forum import create_post


def main():
    # 測試文章數據
    board_id = 1  # 加密貨幣看板
    user_id = "test-user-001"  # TestUser

    # 測試文章 1: BTC 價格分析
    test_post_1 = {
        "category": "市場分析",
        "title": "比特幣短線技術分析 - 關鍵支撈位探討",
        "content": """## 市場概述

近期比特幣價格在 $88,000 附近震盪，成交量持續放大。本文將從技術面分析當前市場狀況。

## 技術指標分析

### RSI 指標
- 14日 RSI 目前處於 55 附近，屬於中性區間
- 未出現超買或超賣信號
- 等待突破信號確認

### MACD
- MACD 柱狀圖接近零軸
- 動能指標顯示多空力量平衡
- 等待金叉或死叉確認

### 移動平均線
- MA20: $87,500 (支撈位)
- MA50: $86,200 (強支撐)
- MA200: $82,000 (長期上升趋势線)

## 關鍵價位

**支撈位:**
- $87,500 (MA20)
- $86,200 (MA50)
- $85,000 (心理支撐)

**阻力位:**
- $89,000 (前期高點)
- $90,500 (關鍵阻力)
- $92,000 (突破目標)

## 交易策略建議

1. **保守型投資者**: 等待突破 $89,000 再進場
2. **積極型投資者**: 可在 $87,500 附近分批建倉
3. **止損設置**: 跌破 $85,000 應止損離場

## 風險提示

> ⚠️ 投資有風險，入場需謹慎。本文僅供參考，不構成投資建議。

## 結論

短期震盪屬於正常現象，長期上升趋势仍然完好。建議關注成交量變化及宏觀經濟數據。

---
*發布時間: 2026-03-31*
*分析師: CryptoMind AI*""",
        "tags": ["BTC", "技術分析", "支撈位", "RSI", "MACD"]
    }

    # 測試文章 2: 以太坊生態分析
    test_post_2 = {
        "category": "生態分析",
        "title": "以太坊 Layer2 生態發展趨勢 - 2026 Q1 回顧",
        "content": """## Layer2 總鎖定價值 (TVL) 概況

截至 2026 年 3 月，以太坊 Layer2 解決方案的總鎖定價值創下新高：

| 平台 | TVL (十億美元) | 增長幅度 |
|------|----------------|----------|
| Arbitrum | $18.5 | +45% |
| Optimism | $12.3 | +62% |
| Base | $8.7 | +120% |
| zkSync Era | $6.2 | +38% |

## 重點發展

### 1. Base 的快速崛起
- Coinbase 推出的 L2 解決方案 Base 在 Q1 表現亮眼
- TVL 增長 120%，超越 zkSync Era
- 生態項目數量突破 500 個

### 2. Arbitrum 的穩健增長
- Stylus 語言開發者生態持續壯大
- DeFi 協議總鎖定價值穩定增長
- Perpetual Protocol V2 上線帶來新活力

### 3. Optimism 的 Superchain 擴展
- Superchain 架構被更多 L2 採用
- OP Stack 成為業界標準
- 跨鏈互操作性大幅提升

## Gas 費用優化

隨著 EIP-4844 的實施，Layer2 交易成本大幅下降：

| 平台 | 平均 Gas 費 | 優化幅度 |
|------|-------------|----------|
| Arbitrum | $0.08 | -65% |
| Optimism | $0.12 | -55% |
| Base | $0.05 | -72% |

## 未來展望

### 短期 (1-3 個月)
- EIP-4844 全面部署
- Proto-Danksharding 測試網上線
- 更多 CeFi 入駐 Layer2

### 中期 (3-6 個月)
- 完整 Danksharding 實施
- 跨鏈標準化
- 隱私計算技術整合

### 長期 (6-12 個月)
- 以太坊成為全球结算层
- 所有活動遷移至 L2
- 單鏈 TPS 達到 100,000+

## 投資建議

關注以下標的：
- $ETH (核心資產)
- $ARB (Arbitrum 治理代幣)
- $OP (Optimism 治理代幣)

---
*數據來源: L2BEAT, DefiLlama*
*更新時間: 2026-03-31*""",
        "tags": ["ETH", "Layer2", "DeFi", "生態分析", "TVL"]
    }

    # 創建測試文章
    print("📝 創建測試文章 1: BTC 技術分析...")
    result1 = create_post(
        board_id=board_id,
        user_id=user_id,
        category=test_post_1["category"],
        title=test_post_1["title"],
        content=test_post_1["content"],
        tags=test_post_1["tags"],
        skip_limit_check=True  # 測試模式跳過限制
    )

    if result1.get("success"):
        print(f"✅ 文章 1 創建成功！Post ID: {result1.get('post_id')}")
    else:
        print(f"❌ 文章 1 創建失敗: {result1.get('error')}")
        return

    print("\n📝 創建測試文章 2: ETH Layer2 分析...")
    result2 = create_post(
        board_id=board_id,
        user_id=user_id,
        category=test_post_2["category"],
        title=test_post_2["title"],
        content=test_post_2["content"],
        tags=test_post_2["tags"],
        skip_limit_check=True
    )

    if result2.get("success"):
        print(f"✅ 文章 2 創建成功！Post ID: {result2.get('post_id')}")
    else:
        print(f"❌ 文章 2 創建失敗: {result2.get('error')}")
        return

    print("\n🎉 測試文章創建完成！")
    print(f"   文章 1 ID: {result1.get('post_id')}")
    print(f"   文章 2 ID: {result2.get('post_id')}")
    print("\n💡 提示: 可以在論壇頁面查看這些測試文章")


if __name__ == "__main__":
    main()
