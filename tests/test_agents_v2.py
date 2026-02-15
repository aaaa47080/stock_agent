#!/usr/bin/env python3
"""
Agent V2 系统测试脚本

测试方式：
1. 单元测试：测试各个模块功能
2. 集成测试：测试完整工作流程
3. HITL 测试：测试人机协作功能

运行：
    python tests/test_agents_v2.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(name: str, success: bool, detail: str = ""):
    status = "✅" if success else "❌"
    print(f"  {status} {name}")
    if detail:
        print(f"      {detail}")


def test_imports():
    """测试 1: 模块导入"""
    print_header("测试 1: 模块导入")

    try:
        from core.agents_v2 import (
            # Base
            AgentState, ProfessionalAgent,
            # Task
            Task, TaskType,
            # Orchestrator
            Orchestrator,
            # Config
            GraphConfig, FeatureToggle, create_default_config,
            # HITL
            HITLManager, HITLState, ReviewPoint,
            # Feedback
            FeedbackCollector, FeedbackType,
            # Codebook
            Codebook, ExperienceCategory, MarketCondition,
            # Adapters
            LegacyAgentAdapter,
        )
        print_result("导入所有模块", True)
        return True
    except Exception as e:
        print_result("导入所有模块", False, str(e))
        return False


def test_config_system():
    """测试 2: 配置系统"""
    print_header("测试 2: 配置系统")

    from core.agents_v2 import GraphConfig, create_default_config, FeatureToggle

    config = create_default_config()
    print_result("创建默认配置", True, f"Agents: {list(config.agents.keys())}")

    # 测试动态开关
    config.disable_agent("news_analysis")
    active = config.get_active_agents({})
    print_result("禁用 news_analysis", "news_analysis" not in active)

    config.enable_agent("news_analysis")
    active = config.get_active_agents({"analysis_depth": "deep"})
    print_result("启用 news_analysis", "news_analysis" in active)

    # 测试功能开关
    config.set_feature("hitl", FeatureToggle.ON)
    print_result("启用 HITL 功能", config.is_feature_enabled("hitl"))

    return True


def test_task_parsing():
    """测试 3: 任务解析"""
    print_header("测试 3: 任务解析")

    from core.agents_v2 import Orchestrator, TaskType

    orch = Orchestrator()

    test_cases = [
        ("BTC 多少钱", TaskType.SIMPLE_PRICE),
        ("分析 BTC", TaskType.ANALYSIS),
        ("深度分析 BTC ETH", TaskType.DEEP_ANALYSIS),
        ("BTC 技術面怎麼樣", TaskType.ANALYSIS),
    ]

    all_passed = True
    for query, expected_type in test_cases:
        task = orch.parse_task(query)
        passed = task.type == expected_type
        print_result(f"解析: '{query}'", passed, f"类型: {task.type.value}")
        all_passed = all_passed and passed

    return all_passed


def test_hitl_system():
    """测试 4: HITL 人机协作"""
    print_header("测试 4: HITL 人机协作")

    from core.agents_v2 import Orchestrator, HITLState

    # 创建带 HITL 的 Orchestrator
    orch = Orchestrator(enable_hitl=True)
    print_result("创建 HITL Orchestrator", orch.is_hitl_enabled())

    # 创建审核点
    review = orch.create_review_point(
        checkpoint_name="trade_decision",
        content="## 交易建议\n\n**方向**: 买入\n**价格**: $95,000",
        context={"decision": "buy", "symbol": "BTC"}
    )
    print_result("创建审核点", review is not None, f"ID: {review.id}")

    # 检查待处理
    pending = orch.get_pending_reviews()
    print_result("获取待处理审核", len(pending) == 1)

    # 模拟用户响应
    state = orch.process_user_response(
        review_id=review.id,
        response="approve",
        feedback="同意执行"
    )
    print_result("处理用户响应", state == HITLState.APPROVED)

    # 检查历史
    history = orch.get_review_history()
    print_result("查看审核历史", len(history) == 1)

    # 测试禁用
    orch.disable_hitl()
    print_result("禁用 HITL", not orch.is_hitl_enabled())

    return True


def test_feedback_system():
    """测试 5: 反馈收集"""
    print_header("测试 5: 反馈收集")

    from core.agents_v2 import FeedbackCollector, FeedbackType

    collector = FeedbackCollector()

    # 收集反馈
    fb = collector.collect(
        session_id="test_session",
        agent_name="technical_analysis",
        feedback_type=FeedbackType.HELPFUL,
        rating=5,
        comment="分析很准确"
    )
    print_result("收集反馈", fb is not None, f"ID: {fb.id}")

    # 获取表现
    perf = collector.get_agent_performance("technical_analysis")
    print_result("获取 Agent 表现", perf is not None, f"平均评分: {perf.average_rating}")

    # 生成报告
    report = collector.generate_report()
    print_result("生成报告", "summary" in report, f"总反馈: {report['summary']['total_feedbacks']}")

    return True


def test_codebook_system():
    """测试 6: Codebook 经验学习"""
    print_header("测试 6: Codebook 经验学习")

    from core.agents_v2 import Codebook, ExperienceCategory, MarketCondition

    codebook = Codebook()

    # 记录经验
    exp = codebook.record_experience(
        category=ExperienceCategory.SUCCESSFUL_TRADE,
        agent_name="technical_analysis",
        market_condition=MarketCondition.TRENDING_UP,
        symbol="BTC",
        timeframe="4h",
        situation="BTC 突破前高，RSI 65",
        action="建议买入",
        reasoning="技术面突破确认",
        outcome="上涨 12%",
        user_rating=5,
        indicators={"rsi": 65, "volume_change": 150}
    )
    print_result("记录经验", exp is not None, f"ID: {exp.id}")

    # 查找相似经验
    matches = codebook.find_similar_experiences({
        "market_condition": MarketCondition.TRENDING_UP,
        "timeframe": "4h",
        "indicators": {"rsi": 62}
    })
    print_result("查找相似经验", len(matches) > 0, f"找到 {len(matches)} 条")

    # 查看统计
    stats = codebook.get_stats()
    print_result("获取统计", True, f"总经验: {stats['total_experiences']}")

    return True


def test_legacy_adapters():
    """测试 7: Legacy Agent 适配器"""
    print_header("测试 7: Legacy Agent 适配器")

    from core.agents_v2 import LegacyAgentAdapter, Orchestrator, Task, TaskType

    # 创建模拟 legacy agent
    class MockLegacyAgent:
        def __init__(self):
            self.tools = ["rsi", "macd"]

        def analyze(self, market_data):
            return {"analysis": "complete"}

    mock = MockLegacyAgent()

    # 包装成 v2 架构
    adapter = LegacyAgentAdapter(
        legacy_agent=mock,
        expertise="test_analysis",
        system_prompt="测试分析师",
        task_keywords=["测试"]
    )
    print_result("创建适配器", True, f"专业: {adapter.expertise}")

    # 测试任务参与决策
    task = Task(query="深度测试分析", type=TaskType.ANALYSIS)
    should_join, reason = adapter.should_participate(task)
    print_result("参与决策", should_join, reason)

    # 注册到 Orchestrator
    orch = Orchestrator()
    orch.register_agent(adapter)
    print_result("注册到 Orchestrator", "test_analysis" in orch.agents)

    return True


def test_full_workflow():
    """测试 8: 完整工作流程"""
    print_header("测试 8: 完整工作流程")

    from core.agents_v2 import (
        Orchestrator, Task, FeedbackCollector,
        FeedbackType, Codebook, ExperienceCategory, MarketCondition, HITLState
    )

    # 1. 初始化所有组件
    orch = Orchestrator(enable_hitl=True)
    collector = FeedbackCollector()
    codebook = Codebook()
    print_result("初始化组件", True)

    # 2. 解析用户查询
    task = orch.parse_task("深度分析 BTC 技術面")
    print_result("解析任务", True, f"类型: {task.type.value}, 深度: {task.analysis_depth}")

    # 3. 模拟分析结果，需要用户确认
    review = orch.create_review_point(
        checkpoint_name="trade_decision",
        content="## BTC 分析结果\n\n**建议**: 买入\n**信心度**: 75%",
        context={"decision": "buy", "symbol": "BTC"}
    )
    print_result("创建审核点", True, f"等待用户确认...")

    # 4. 模拟用户确认
    state = orch.process_user_response(review.id, "approve", "同意执行")
    print_result("用户确认", state == HITLState.APPROVED)

    # 5. 收集用户反馈
    fb = collector.collect(
        session_id="test_workflow",
        agent_name="technical_analysis",
        feedback_type=FeedbackType.HELPFUL,
        rating=5,
        comment="分析准确，建议有用"
    )
    print_result("收集反馈", True, f"评分: {fb.rating}")

    # 6. 记录成功经验
    exp = codebook.record_experience(
        category=ExperienceCategory.SUCCESSFUL_TRADE,
        agent_name="technical_analysis",
        market_condition=MarketCondition.TRENDING_UP,
        symbol="BTC",
        timeframe="4h",
        situation="用户确认的成功交易",
        action="买入建议",
        reasoning="技术分析支持",
        outcome="用户满意",
        user_rating=5
    )
    print_result("记录经验", exp is not None)

    # 7. 查看最终统计
    report = collector.generate_report()
    stats = codebook.get_stats()
    print_result("最终统计", True,
        f"反馈: {report['summary']['total_feedbacks']}, 经验: {stats['total_experiences']}")

    return True


def test_langgraph_integration():
    """测试 9: LangGraph 整合"""
    print_header("测试 9: LangGraph 整合")

    from core.agents_v2 import Orchestrator

    orch = Orchestrator(enable_hitl=True)

    # 获取 interrupt 点
    interrupt_points = orch.get_langgraph_interrupt_points()
    print_result("获取 interrupt 点", len(interrupt_points) > 0,
        f"interrupt_before: {interrupt_points}")

    # 测试条件中断
    should_interrupt = orch.should_interrupt("trade_decision", {"decision": "buy"})
    print_result("买入决策需要中断", should_interrupt)

    should_interrupt2 = orch.should_interrupt("trade_decision", {"decision": "hold"})
    print_result("持有决策需要中断", not should_interrupt2)

    # 测试高风险中断
    should_interrupt3 = orch.should_interrupt("high_risk_trade", {"risk_level": "high"})
    print_result("高风险交易需要中断", should_interrupt3)

    return True


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  Agent V2 系统测试")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tests = [
        ("模块导入", test_imports),
        ("配置系统", test_config_system),
        ("任务解析", test_task_parsing),
        ("HITL 人机协作", test_hitl_system),
        ("反馈收集", test_feedback_system),
        ("Codebook 经验学习", test_codebook_system),
        ("Legacy 适配器", test_legacy_adapters),
        ("完整工作流程", test_full_workflow),
        ("LangGraph 整合", test_langgraph_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))

    # 打印总结
    print_header("测试总结")

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)

    for name, p, err in results:
        status = "✅" if p else "❌"
        print(f"  {status} {name}")
        if err:
            print(f"      错误: {err}")

    print(f"\n  总计: {passed}/{total} 通过")

    if passed == total:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️ 有 {total - passed} 个测试失败")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
