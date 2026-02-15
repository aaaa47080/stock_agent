#!/usr/bin/env python3
"""
Agent V2 交互式聊天测试界面

运行方式：
    python3 chat_v2.py

功能：
- 像聊天机器人一样与 Agent 交互
- 测试任务解析
- 测试 HITL 人机协作
- 查看系统状态
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from core.agents_v2 import (
    Orchestrator,
    FeedbackCollector,
    Codebook,
    FeedbackType,
    ExperienceCategory,
    MarketCondition,
    HITLState,
    create_default_config,
)


class ChatBot:
    """交互式聊天机器人"""

    def __init__(self):
        self.orch = Orchestrator(enable_hitl=True)
        self.collector = FeedbackCollector()
        self.codebook = Codebook()
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.pending_review = None
        self.analysis_history = []

    def clear_screen(self):
        """清屏（使用 ANSI escape code）"""
        print("\033[2J\033[H", end="")

    def print_banner(self):
        print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🤖 Agent V2 交互式测试界面                            ║
║                                                           ║
║     指令：                                                ║
║       /help     - 显示帮助                               ║
║       /status   - 查看系统状态                           ║
║       /config   - 查看配置                               ║
║       /history  - 查看分析历史                           ║
║       /feedback - 提交反馈                               ║
║       /codebook - 查看经验库                             ║
║       /hitl     - 开关人机协作                           ║
║       /clear    - 清屏                                   ║
║       /quit     - 退出                                   ║
║                                                           ║
║     或直接输入问题，如：                                  ║
║       "分析 BTC"                                          ║
║       "ETH 技术面怎么样"                                  ║
║       "深度分析 SOL"                                      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
        """)

    def process_query(self, query: str) -> str:
        """处理用户查询"""
        query = query.strip()

        # 处理指令
        if query.startswith("/"):
            return self.handle_command(query)

        # 检查是否有待处理的审核
        if self.pending_review:
            return self.handle_review_response(query)

        # 解析任务
        return self.analyze(query)

    def analyze(self, query: str) -> str:
        """分析用户查询"""
        # 解析任务
        task = self.orch.parse_task(query)

        output = []
        output.append(f"\n📋 任务解析结果")
        output.append("─" * 40)
        output.append(f"  查询: {query}")
        output.append(f"  类型: {task.type.value}")
        output.append(f"  符号: {', '.join(task.symbols)}")
        output.append(f"  深度: {task.analysis_depth}")
        output.append(f"  回测: {'是' if task.needs_backtest else '否'}")

        # 模拟分析结果
        output.append(f"\n🔍 分析结果")
        output.append("─" * 40)

        symbol = task.symbols[0] if task.symbols else "BTC"

        if task.type.value == "simple_price":
            output.append(f"  💰 {symbol} 当前价格查询")
            output.append(f"  （实际价格需要连接 API）")
        else:
            output.append(f"  📊 {symbol} 分析中...")
            output.append(f"  ✓ 技术指标分析")
            output.append(f"  ✓ 市场情绪评估")
            if task.analysis_depth == "deep":
                output.append(f"  ✓ 新闻分析")
                output.append(f"  ✓ 深度辩论")

            # 如果是交易决策，触发 HITL
            if self.orch.is_hitl_enabled() and task.type.value != "simple_price":
                output.append(f"\n")
                output.append(self.create_review(symbol, task))

        # 记录历史
        self.analysis_history.append({
            "query": query,
            "task": task.type.value,
            "symbols": task.symbols,
            "time": datetime.now().isoformat()
        })

        return "\n".join(output)

    def create_review(self, symbol: str, task) -> str:
        """创建审核点"""
        # 随机生成模拟建议
        import random
        decisions = [
            ("买入", "看涨", "70%"),
            ("卖出", "看跌", "65%"),
            ("持有", "中性", "55%"),
        ]
        decision, bias, confidence = random.choice(decisions)

        content = f"""
## {symbol} 交易建议

**方向**: {decision}
**偏向**: {bias}
**信心度**: {confidence}

**分析要点**:
- 技术指标显示 {bias}信号
- 市场情绪偏{'乐观' if bias == '看涨' else '谨慎'}
- 建议仓位: 10-20%

**风险提示**:
- 设置止损 -5%
- 关注市场变化
"""

        self.pending_review = self.orch.create_review_point(
            checkpoint_name="trade_decision",
            content=content,
            context={"decision": decision, "symbol": symbol}
        )

        output = []
        output.append("🔔 需要您的确认")
        output.append("─" * 40)
        output.append(content)
        output.append("─" * 40)
        output.append("请选择：")
        output.append("  1 或 ✅ - 同意执行")
        output.append("  2 或 ❌ - 拒绝执行")
        output.append("  3 或 💬 - 有疑问（进入讨论）")
        output.append("  4 或 📝 - 修改参数")
        output.append("")

        return "\n".join(output)

    def handle_review_response(self, response: str) -> str:
        """处理用户对审核的响应"""
        response_map = {
            "1": "approve", "✅": "approve", "同意": "approve", "y": "approve", "yes": "approve",
            "2": "reject", "❌": "reject", "拒绝": "reject", "n": "reject", "no": "reject",
            "3": "discuss", "💬": "discuss", "疑问": "discuss", "?": "discuss",
            "4": "modify", "📝": "modify", "修改": "modify",
        }

        action = response_map.get(response.lower(), None)

        if not action:
            return "❓ 无效选择，请输入 1-4 或对应的表情符号"

        state = self.orch.process_user_response(
            review_id=self.pending_review.id,
            response=action,
            feedback=None
        )

        output = []
        output.append(f"\n{'='*40}")
        output.append(f"  您的选择: {action}")
        output.append(f"  状态: {state.value}")
        output.append(f"{'='*40}\n")

        if action == "approve":
            output.append("✅ 交易已批准！正在执行...")
            output.append("（实际执行需要连接交易 API）")
        elif action == "reject":
            output.append("❌ 交易已拒绝。")
        elif action == "discuss":
            output.append("💬 进入讨论模式...")
            output.append("请输入您的问题或疑虑：")
        elif action == "modify":
            output.append("📝 请输入修改建议：")

        self.pending_review = None
        return "\n".join(output)

    def handle_command(self, cmd: str) -> str:
        """处理指令"""
        cmd = cmd.lower().strip()

        if cmd == "/help":
            return self.show_help()
        elif cmd == "/status":
            return self.show_status()
        elif cmd == "/config":
            return self.show_config()
        elif cmd == "/history":
            return self.show_history()
        elif cmd == "/feedback":
            return "📊 反馈功能：在分析后输入 'feedback 5 很准确' 来提交反馈"
        elif cmd == "/codebook":
            return self.show_codebook()
        elif cmd == "/hitl":
            return self.toggle_hitl()
        elif cmd == "/clear":
            self.clear_screen()
            self.print_banner()
            return ""
        elif cmd == "/quit":
            return "QUIT"
        else:
            return f"❓ 未知指令: {cmd}\n输入 /help 查看可用指令"

    def show_help(self) -> str:
        return """
📖 帮助信息

基本使用:
  直接输入问题，如 "分析 BTC" 或 "ETH 怎么样"

指令列表:
  /help     - 显示此帮助
  /status   - 查看系统状态（HITL、反馈、经验库）
  /config   - 查看当前配置
  /history  - 查看分析历史
  /feedback - 提交反馈（格式: feedback <评分> <评论>）
  /codebook - 查看经验库
  /hitl     - 开关人机协作模式
  /clear    - 清屏
  /quit     - 退出程序

人机协作 (HITL):
  当系统需要确认时，会显示选项：
    1/✅ - 同意
    2/❌ - 拒绝
    3/💬 - 讨论
    4/📝 - 修改

示例:
  > 分析 BTC
  > 深度分析 ETH
  > SOL 技术面
  > feedback 5 分析很准确
        """

    def show_status(self) -> str:
        stats = self.codebook.get_stats()
        report = self.collector.generate_report()

        return f"""
📊 系统状态

会话 ID: {self.session_id}

HITL 状态:
  启用: {'✅' if self.orch.is_hitl_enabled() else '❌'}
  待处理审核: {len(self.orch.get_pending_reviews())}
  审核历史: {len(self.orch.get_review_history())}

反馈收集:
  总反馈: {report['summary']['total_feedbacks']}
  平均评分: {report['summary']['average_rating']}
  帮助率: {report['summary']['helpful_rate']:.0%}

经验库:
  总经验: {stats['total_experiences']}
  平均评分: {stats['avg_rating']}

分析历史:
  本次会话分析: {len(self.analysis_history)} 次
        """

    def show_config(self) -> str:
        config = self.orch.config
        return f"""
⚙️ 当前配置

Agents:
{chr(10).join(f'  - {name}: {"启用" if cfg.enabled else "禁用"}' for name, cfg in config.agents.items())}

功能开关:
  multi_timeframe: {config.features.get('multi_timeframe').value}
  debate: {config.features.get('debate').value}
  risk_assessment: {config.features.get('risk_assessment').value}
  hitl: {config.features.get('hitl').value}
  codebook: {config.features.get('codebook').value}
        """

    def show_history(self) -> str:
        if not self.analysis_history:
            return "📭 暂无分析历史"

        output = ["📜 分析历史\n"]
        for i, h in enumerate(self.analysis_history[-10:], 1):
            output.append(f"{i}. [{h['time'][:16]}] {h['query']}")
            output.append(f"   类型: {h['task']}, 符号: {', '.join(h['symbols'])}")

        return "\n".join(output)

    def show_codebook(self) -> str:
        stats = self.codebook.get_stats()
        top = self.codebook.get_top_experiences(5)

        output = [f"""
📚 经验库

统计:
  总经验: {stats['total_experiences']}
  按类别: {stats['by_category']}
  按 Agent: {stats['by_agent']}
"""]

        if top:
            output.append("热门经验:")
            for exp in top:
                output.append(f"  - {exp.symbol} {exp.action} ({exp.user_rating}⭐)")

        return "\n".join(output)

    def toggle_hitl(self) -> str:
        if self.orch.is_hitl_enabled():
            self.orch.disable_hitl()
            return "🔴 HITL 已禁用（所有决策自动批准）"
        else:
            self.orch.enable_hitl()
            return "🟢 HITL 已启用（关键决策需要确认）"

    def run(self):
        """运行交互循环"""
        self.print_banner()

        while True:
            try:
                # 显示提示符
                if self.pending_review:
                    prompt = "\n待确认 > "
                else:
                    prompt = "\n💬 > "

                query = input(prompt).strip()

                if not query:
                    continue

                # 处理反馈提交
                if query.lower().startswith("feedback "):
                    parts = query.split(maxsplit=2)
                    if len(parts) >= 2:
                        rating = int(parts[1])
                        comment = parts[2] if len(parts) > 2 else ""
                        self.collector.collect(
                            session_id=self.session_id,
                            agent_name="user_input",
                            feedback_type=FeedbackType.HELPFUL if rating >= 4 else FeedbackType.NOT_HELPFUL,
                            rating=rating,
                            comment=comment
                        )
                        print(f"\n✅ 反馈已提交: {rating}⭐ {comment}")
                        continue

                # 处理查询
                result = self.process_query(query)

                if result == "QUIT":
                    print("\n👋 再见！")
                    break

                if result:
                    print(result)

            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                print(f"\n❌ 错误: {e}")


def main():
    bot = ChatBot()
    bot.run()


if __name__ == "__main__":
    main()
