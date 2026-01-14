"""
工具輸出格式化函數
將分析結果格式化為可讀的 Markdown 文本
"""


def format_full_analysis_result(result: dict, market_type: str, symbol: str, interval: str) -> str:
    """
    格式化完整分析結果為可讀文本

    Args:
        result: LangGraph 分析結果
        market_type: 市場類型（現貨/合約）
        symbol: 交易對符號
        interval: 時間週期

    Returns:
        格式化的 Markdown 文本
    """
    current_price = result.get('current_price', 0)
    final_approval = result.get('final_approval')
    trader_decision = result.get('trader_decision')
    risk_assessment = result.get('risk_assessment')
    debate_judgment = result.get('debate_judgment')
    analyst_reports = result.get('analyst_reports', [])

    output = f"""## {symbol} {market_type}分析報告 ({interval})

### 當前價格
**${current_price:.4f}**

"""

    # 分析師報告摘要
    if analyst_reports:
        output += "### 分析師觀點摘要\n"
        for report in analyst_reports:
            if report:
                bullish = len(getattr(report, 'bullish_points', []))
                bearish = len(getattr(report, 'bearish_points', []))
                output += f"- **{report.analyst_type}**: {bullish}個看多觀點 / {bearish}個看空觀點\n"
        output += "\n"

    # 辯論結果
    if debate_judgment:
        output += f"""### 多空辯論裁決
| 項目 | 結果 |
|------|------|
| 勝出方 | **{debate_judgment.winning_stance}** |
| 建議行動 | **{debate_judgment.suggested_action}** |

**獲勝原因**: {debate_judgment.winning_reason}

**多頭最強論點**: {debate_judgment.strongest_bull_point}

**空頭最強論點**: {debate_judgment.strongest_bear_point}

"""
        if debate_judgment.fatal_flaw:
            output += f"⚠️ **致命缺陷**: {debate_judgment.fatal_flaw}\n\n"

        output += f"**核心事實**: {debate_judgment.key_takeaway}\n\n"

    # 交易決策
    if trader_decision:
        entry = f"${trader_decision.entry_price:.4f}" if trader_decision.entry_price else "N/A"
        stop_loss = f"${trader_decision.stop_loss:.4f}" if trader_decision.stop_loss else "N/A"
        take_profit = f"${trader_decision.take_profit:.4f}" if trader_decision.take_profit else "N/A"
        follows_text = "✅ 是" if trader_decision.follows_judge else "⚠️ 否"

        output += f"""### 交易決策
| 項目 | 建議 |
|------|------|
| **決策** | **{trader_decision.decision}** |
| 進場價 | {entry} |
| 止損 | {stop_loss} |
| 止盈 | {take_profit} |
| 建議倉位 | {trader_decision.position_size * 100:.1f}% |
| 遵循裁判 | {follows_text} |

**決策理由**: {trader_decision.reasoning}

**主要風險**: {trader_decision.key_risk}

"""
        if not trader_decision.follows_judge and trader_decision.deviation_reason:
            output += f"⚠️ **偏離裁判原因**: {trader_decision.deviation_reason}\n\n"

    # 風險評估
    if risk_assessment:
        output += f"""### 風險評估
- **風險等級**: {risk_assessment.risk_level}
- **評估意見**: {risk_assessment.assessment}
- **調整後倉位**: {risk_assessment.adjusted_position_size * 100:.1f}%
"""
        if risk_assessment.warnings:
            output += f"- **警告**: {', '.join(risk_assessment.warnings)}\n"
        output += "\n"

    # 最終審批
    if final_approval:
        output += f"""### 最終審批 (基金經理)
| 項目 | 結果 |
|------|------|
| **最終決定** | **{final_approval.final_decision}** |
| 最終倉位 | {final_approval.final_position_size * 100:.1f}% |

**執行建議**: {final_approval.execution_notes}

**審批理由**: {final_approval.rationale}
"""

    # 附錄：真實新聞列表
    market_data = result.get('market_data', {})
    news_data = market_data.get('新聞資訊', [])
    if news_data:
        output += "\n### 📰 相關新聞快訊\n\n"
        for i, news in enumerate(news_data[:5], 1):
            title = news.get('title', 'N/A')
            url = news.get('url', '')
            source = news.get('source', 'Unknown')

            if url:
                output += f"{i}. [**{title}**]({url}) - {source}\n"
            else:
                output += f"{i}. **{title}** - {source}\n"
        output += "\n"

    output += "\n> 免責聲明：以上分析僅供參考，不構成投資建議。投資有風險，請謹慎決策。"

    return output


def format_compact_analysis_result(result: dict, market_type: str, symbol: str, interval: str) -> str:
    """
    格式化簡潔版分析結果（適合辯論過程已即時輸出的情況）

    Args:
        result: LangGraph 分析結果
        market_type: 市場類型（現貨/合約）
        symbol: 交易對符號
        interval: 時間週期

    Returns:
        格式化的簡潔 Markdown 文本
    """
    current_price = result.get('current_price', 0)
    final_approval = result.get('final_approval')
    trader_decision = result.get('trader_decision')
    risk_assessment = result.get('risk_assessment')
    debate_judgment = result.get('debate_judgment')

    output = f"""## {symbol} {market_type}分析結論 ({interval})

"""

    # 核心決策卡片
    if final_approval:
        decision_emoji = "🟢" if "買入" in final_approval.final_decision or "做多" in final_approval.final_decision else \
                        "🔴" if "賣出" in final_approval.final_decision or "做空" in final_approval.final_decision else "🟡"

        output += f"""### {decision_emoji} 最終決策: **{final_approval.final_decision}**

| 項目 | 數值 |
|------|------|
| 當前價格 | **${current_price:.4f}** |
| 建議倉位 | **{final_approval.final_position_size * 100:.1f}%** |
"""

    # 交易建議（關鍵數字）
    if trader_decision:
        entry = f"${trader_decision.entry_price:.4f}" if trader_decision.entry_price else "-"
        stop_loss = f"${trader_decision.stop_loss:.4f}" if trader_decision.stop_loss else "-"
        take_profit = f"${trader_decision.take_profit:.4f}" if trader_decision.take_profit else "-"

        output += f"""| 進場價 | {entry} |
| 止損 | {stop_loss} |
| 止盈 | {take_profit} |

"""

    # 風險等級（一行）
    if risk_assessment:
        risk_emoji = "🟢" if risk_assessment.risk_level in ["低", "Low"] else \
                    "🟡" if risk_assessment.risk_level in ["中", "Medium"] else "🔴"
        output += f"**風險等級**: {risk_emoji} {risk_assessment.risk_level}\n\n"

    # 執行建議（簡短）
    if final_approval and final_approval.execution_notes:
        output += f"**執行建議**: {final_approval.execution_notes}\n\n"

    # 辯論結論（簡化）
    if debate_judgment:
        output += f"**辯論結論**: {debate_judgment.winning_stance}勝出 → {debate_judgment.suggested_action}\n\n"

    # 相關新聞（保留）
    market_data = result.get('market_data', {})
    news_data = market_data.get('新聞資訊', [])
    if news_data:
        output += "### 📰 相關新聞\n\n"
        for i, news in enumerate(news_data[:3], 1):  # 只顯示前3則
            title = news.get('title', 'N/A')
            url = news.get('url', '')
            source = news.get('source', 'Unknown')

            if url:
                output += f"{i}. [**{title}**]({url}) - {source}\n"
            else:
                output += f"{i}. **{title}** - {source}\n"
        output += "\n"

    output += "> 免責聲明：以上分析僅供參考，不構成投資建議。"

    return output
