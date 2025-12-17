import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import AnalystReport, ResearcherDebate, TraderDecision, RiskAssessment, FinalApproval
from typing import Dict, List

def _display_single_market_report(
    market_name: str,
    analyst_reports: List[AnalystReport],
    bull_argument: ResearcherDebate,
    bear_argument: ResearcherDebate,
    trader_decision: TraderDecision,
    risk_assessment: RiskAssessment,
    final_approval: FinalApproval,
    current_price: float,
    market_type: str,
    market_data: Dict
):
    """顯示單一市場的決策報告"""
    
    print(f"\n" + "=" * 100)
    print(f"📊 {market_name} 市場分析報告")
    print("=" * 100)
    
    # Report Header
    print(f"市場類型: {market_type.capitalize()}")
    if market_type == 'futures' and trader_decision.leverage:
        print(f"建議槓桿: {trader_decision.leverage}x")

    # 分析師報告
    print("\n【第一層：分析師團隊報告】")
    print("-" * 100)
    for report in analyst_reports:
        print(f"\n{report.analyst_type} (信心度: {report.confidence}%)")
        print(f"摘要：{report.summary}")
        if report.bullish_points:
            print(f"看漲點：{', '.join(report.bullish_points[:3])}")
        if report.bearish_points:
            print(f"看跌點：{', '.join(report.bearish_points[:3])}")
    
    # 研究員辯論
    print("\n【第二層：研究團隊辯論】")
    print("-" * 100)
    print(f"\n🐂 多頭研究員 (信心度: {bull_argument.confidence}%)")
    print(f"論點：{bull_argument.argument}")
    print(f"關鍵點：")
    for point in bull_argument.key_points:
        print(f"  • {point}")
    
    print(f"\n🐻 空頭研究員 (信心度: {bear_argument.confidence}%)")
    print(f"論點：{bear_argument.argument}")
    print(f"關鍵點：")
    for point in bear_argument.key_points:
        print(f"  • {point}")
    
    # 交易員決策
    print("\n【第三層：交易員決策】")
    print("-" * 100)
    print(f"決策：{trader_decision.decision}")
    print(f"信心度：{trader_decision.confidence}%")
    print(f"建議倉位：{trader_decision.position_size * 100:.0f}%")
    if market_type == 'futures' and trader_decision.leverage:
        print(f"使用槓桿：{trader_decision.leverage}x")
    
    if trader_decision.entry_price is not None:
        print(f"進場價：${trader_decision.entry_price:.2f}")
    else:
        print("進場價：N/A")

    # Calculate percentage based on entry price for both stop-loss and take-profit
    # For futures, if Short, invert the percentage for display
    if trader_decision.stop_loss is not None and trader_decision.entry_price is not None and trader_decision.entry_price > 0:
        percentage = ((trader_decision.stop_loss / trader_decision.entry_price - 1) * 100)
        if trader_decision.decision == 'Short': # For short, a stop_loss above entry is a loss
            percentage = -percentage
        print(f"止損價：${trader_decision.stop_loss:.2f} ({percentage:.2f}%)")
    else:
        print("止損價：N/A")

    if trader_decision.take_profit is not None and trader_decision.entry_price is not None and trader_decision.entry_price > 0:
        percentage = ((trader_decision.take_profit / trader_decision.entry_price - 1) * 100)
        if trader_decision.decision == 'Short': # For short, a take_profit below entry is a profit
            percentage = -percentage
        print(f"止盈價：${trader_decision.take_profit:.2f} ({percentage:.2f}%)")
    else:
        print("止盈價：N/A")
        
    print(f"\n推理過程：{trader_decision.reasoning}")
    print(f"\n綜合評估：{trader_decision.synthesis}")
    
    # 風險評估
    print("\n【第四層：風險管理評估】")
    print("-" * 100)
    print(f"風險等級：{risk_assessment.risk_level}")
    print(f"風險經理批准：{'✅ 是' if risk_assessment.approve else '❌ 否'}")
    print(f"調整後倉位：{risk_assessment.adjusted_position_size * 100:.0f}%")
    print(f"評估：{risk_assessment.assessment}")
    if risk_assessment.warnings:
        print(f"\n⚠️ 風險警告：")
        for warning in risk_assessment.warnings:
            print(f"  • {warning}")
    if market_type == 'futures' and market_data.get('funding_rate_info'):
        fr_info = market_data['funding_rate_info']
        print(f"\n資金費率：{fr_info.get('last_funding_rate', 'N/A')}")
        print(f"下次資金費率時間：{fr_info.get('next_funding_time', 'N/A')}")
    print(f"\n建議調整：{risk_assessment.suggested_adjustments}")
    
    # 最終審批
    print("\n【第五層：基金經理最終審批】")
    print("-" * 100)
    print(f"最終決定：{final_approval.final_decision}")
    print(f"是否批准：{'✅ 批准' if final_approval.approved else '❌ 拒絕'}")
    print(f"最終倉位：{final_approval.final_position_size * 100:.0f}%")
    print(f"執行指示：{final_approval.execution_notes}")
    print(f"批准理由：{final_approval.rationale}")
    
    # 最終建議
    print("\n" + "=" * 100)
    print("🎯 最終執行建議")
    print("=" * 100)

    # 顯示交易動作
    trading_action = trader_decision.decision
    action_map = {
        "Buy": "🟢 買入",
        "Sell": "🔴 賣出",
        "Hold": "⏸️ 觀望",
        "Long": "🟢 做多",
        "Short": "🔴 做空"
    }
    action_display = action_map.get(trading_action, trading_action)
    print(f"交易動作：{action_display}")

    # 顯示審批結果
    approval_map = {
        "Approve": "✅ 完全批准",
        "Amended": "⚠️ 修正後批准",
        "Reject": "❌ 拒絕",
        "Hold": "⏸️ 觀望"
    }
    approval_display = approval_map.get(final_approval.final_decision, final_approval.final_decision)
    print(f"審批結果：{approval_display}")

    if final_approval.approved:
        print(f"執行倉位：{final_approval.final_position_size * 100:.0f}%")
        if market_type == 'futures' and final_approval.approved_leverage is not None:
            print(f"使用槓桿：{final_approval.approved_leverage}x")
        print(f"\n💰 價格資訊：")
        print(f"  當前價格：${current_price:.2f}")
        if final_approval.final_position_size > 0:
            if trader_decision.entry_price is not None:
                print(f"  建議進場價：${trader_decision.entry_price:.2f}")
            else:
                print(f"  建議進場價：N/A（使用當前價格 ${current_price:.2f}）")
            if trader_decision.stop_loss is not None:
                loss_pct = abs((trader_decision.stop_loss - current_price) / current_price * 100)
                print(f"  止損價位：${trader_decision.stop_loss:.2f} ({'-' if trader_decision.stop_loss < current_price else '+'}{loss_pct:.2f}%)")
            else:
                print("  止損價位：N/A")
            if trader_decision.take_profit is not None:
                profit_pct = abs((trader_decision.take_profit - current_price) / current_price * 100)
                print(f"  止盈價位：${trader_decision.take_profit:.2f} ({'+' if trader_decision.take_profit > current_price else '-'}{profit_pct:.2f}%)")
            else:
                print("  止盈價位：N/A")
    else:
        print("⏸️ 建議觀望，等待更好的機會")
    
    print("\n" + "=" * 100)
    print("報告結束")
    print("=" * 100)

def display_full_report(spot_results: Dict, futures_results: Dict):
    """
    顯示完整的決策報告，包含現貨和合約市場。
    """
    
    # 現貨市場報告
    if spot_results.get("analyst_reports"):
        _display_single_market_report(
            market_name="現貨 (Spot)",
            analyst_reports=spot_results['analyst_reports'],
            bull_argument=spot_results['bull_argument'],
            bear_argument=spot_results['bear_argument'],
            trader_decision=spot_results['trader_decision'],
            risk_assessment=spot_results['risk_assessment'],
            final_approval=spot_results['final_approval'],
            current_price=spot_results['current_price'],
            market_type=spot_results['market_data']['market_type'],
            market_data=spot_results['market_data']
        )
    else:
        print("\n" + "=" * 100)
        print("📊 現貨 (Spot) 市場分析報告：工作流未成功生成報告。")
        print("=" * 100)

    # 合約市場報告
    if futures_results.get("analyst_reports"):
        _display_single_market_report(
            market_name="合約 (Futures)",
            analyst_reports=futures_results['analyst_reports'],
            bull_argument=futures_results['bull_argument'],
            bear_argument=futures_results['bear_argument'],
            trader_decision=futures_results['trader_decision'],
            risk_assessment=futures_results['risk_assessment'],
            final_approval=futures_results['final_approval'],
            current_price=futures_results['current_price'],
            market_type=futures_results['market_data']['market_type'],
            market_data=futures_results['market_data']
        )
    else:
        print("\n" + "=" * 100)
        print("📊 合約 (Futures) 市場分析報告：工作流未成功生成報告。")
        print("=" * 100)

    print("\n\n" + "=" * 100)
    print("✅ 雙市場綜合分析報告結束")
    print("=" * 100)
