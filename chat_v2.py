#!/usr/bin/env python3
"""
Agent V2 交互式聊天测试界面

运行方式：
    python3 chat_v2.py

功能：
- 像聊天机器人一样与 Agent 交互
- 所有任务解析使用 LLM（不再是硬編碼規則）
- 测试 HITL 人机协作
- 查看系统状态
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_core.language_models import BaseChatModel

from utils.llm_client import LLMClientFactory
from utils.utils import get_crypto_news_google, get_crypto_news
from core.agents_v2 import (
    Orchestrator,
    FeedbackCollector,
    Codebook,
    FeedbackType,
    ExperienceCategory,
    MarketCondition,
    HITLState,
    create_default_config,
    LLMTaskParser,
    ConversationMemory,
)


class ChatBot:
    """交互式聊天机器人 - 完全由 LLM 驱动"""

    def __init__(self, llm_client: BaseChatModel = None):
        """
        初始化 ChatBot

        Args:
            llm_client: LangChain LLM client（如果未提供，会自动创建）
        """
        # 必须有 LLM client
        self.llm_client = llm_client or LLMClientFactory.create_client("openai", "gpt-4o-mini")

        # Orchestrator 使用同样的 LLM client
        self.orch = Orchestrator(llm_client=self.llm_client, enable_hitl=True)
        self.parser = LLMTaskParser(self.llm_client)

        self.collector = FeedbackCollector()
        self.codebook = Codebook()
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.pending_review = None
        self.analysis_history = []

        # Phase 2: 对话记忆系统
        self.memory = ConversationMemory()
        self.message_history = []  # 完整消息历史

    def classify_intent(self, query: str) -> str:
        """
        使用 LLM 分类用户意图（完全由 LLM 驱动，支持对话上下文）

        Returns:
            "greeting" - 问候/闲聊
            "crypto_analysis" - 加密货币分析
            "follow_up" - 跟进问题（如「刚才那个怎么样」「它呢」）
            "general_chat" - 一般闲聊、其他话题
            "memory_query" - 询问之前的对话内容
        """
        # 构建上下文
        context = self._get_recent_context()

        prompt = f"""判断以下用户输入的意图，只回复一个类别：

{context}

当前用户输入：{query}

类别选项：
- greeting: 问候、打招呼
- crypto_analysis: 加密货币/股票分析、价格查询、技术分析、投资建议
- news_query: 新闻查询（如「最新新闻」「有什么新闻」「Pi Network 新闻」）
- follow_up: 跟进问题（如「刚才那个怎么样」「它呢」「继续」）
- general_chat: 一般闲聊、其他话题（如天气、笑话等）
- memory_query: 询问之前的对话内容（如「我问了什么」「刚才说了什么」）

只回复类别名称，不要其他内容。"""

        try:
            response = self.llm_client.invoke([HumanMessage(content=prompt)])
            intent = response.content.strip().lower()

            # 标准化
            if "greeting" in intent:
                return "greeting"
            elif "news" in intent:
                return "news_query"
            elif "crypto" in intent or "analysis" in intent:
                return "crypto_analysis"
            elif "follow" in intent:
                return "follow_up"
            elif "memory" in intent:
                return "memory_query"
            elif "general" in intent or "chat" in intent:
                return "general_chat"
            else:
                return "general_chat"

        except Exception as e:
            print(f"[意圖分類錯誤: {e}]")
            return "general_chat"

    def _get_recent_context(self) -> str:
        """构建最近对话上下文（用于意图分类）"""
        if not self.message_history:
            return "（这是对话的开始，没有之前的对话历史）"

        recent = self.message_history[-6:]  # 最近 3 轮对话
        context_parts = ["最近的对话："]

        for msg in recent:
            role = "用户" if msg["role"] == "user" else "助手"
            # 截断过长的消息
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            context_parts.append(f"  {role}: {content}")

        return "\n".join(context_parts)

    def _build_conversation_context(self) -> str:
        """构建对话上下文（用于 LLM 回复生成）"""
        context_parts = []

        # 添加分析历史
        if self.analysis_history:
            recent = self.analysis_history[-3:]
            context_parts.append("最近分析过的内容：")
            for h in recent:
                symbols = ', '.join(h['symbols']) if h['symbols'] else '无'
                context_parts.append(f"  - {h['query']} (符号: {symbols})")

        # 添加消息历史
        if self.message_history:
            recent_msgs = self.message_history[-6:]
            if context_parts:
                context_parts.append("")  # 空行
            context_parts.append("最近的对话：")
            for msg in recent_msgs:
                role = "用户" if msg["role"] == "user" else "助手"
                content = msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
                context_parts.append(f"  {role}: {content}")

        return "\n".join(context_parts) if context_parts else ""

    def handle_general_chat(self, query: str, intent: str = None) -> str:
        """处理普通对话（使用 LLM 生成智能回复）"""

        # 构建包含对话历史的 prompt
        context = self._build_conversation_context()

        prompt = f"""你是 Agent V2，一个友善的 AI 助手。你的主要专长是加密货币分析，但你也可以进行自然对话。

{context}

用户输入：{query}

请用繁体中文简短回覆（2-3 句话）。

回复原则：
- 如果是问候，友善回应
- 如果是问你的功能，说明你可以分析加密货币（BTC, ETH, SOL 等）
- 如果是其他问题（如天气、闲聊），自然地回应，并适时引导回你的专长
- 不要生硬地拒绝用户，保持友善和对话流畅性
- 如果用户之前分析过某个币种，可以提及作为上下文"""

        try:
            response = self.llm_client.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            return f"[回覆生成錯誤: {e}]\n請輸入 /help 查看功能。"

    def handle_follow_up(self, query: str) -> str:
        """处理跟进问题（利用对话记忆）"""

        # 获取最近的上下文
        ctx = self.memory.get_or_create(self.session_id)

        # 检查是否有历史符号
        if ctx.symbols_mentioned:
            last_symbol = ctx.symbols_mentioned[-1]
            # 将跟进问题转换为完整分析请求
            enhanced_query = f"{last_symbol} {query}"
            return self.analyze(enhanced_query)

        # 检查分析历史
        if self.analysis_history:
            last_analysis = self.analysis_history[-1]
            if last_analysis.get('symbols'):
                last_symbol = last_analysis['symbols'][0]
                enhanced_query = f"{last_symbol} {query}"
                return self.analyze(enhanced_query)

        # 没有历史符号，询问用户
        return "🤔 我不确定你指的是哪个币种。请明确告诉我你想了解哪个加密货币，例如「BTC 怎么样」"

    def handle_memory_query(self, query: str) -> str:
        """处理记忆查询（用户询问之前的对话内容）"""

        # 构建对话摘要
        context = self._build_conversation_context()

        prompt = f"""用户想知道之前对话的内容。

{context}

用户问题：{query}

请用繁体中文友善地回答，总结用户之前问过的问题和你分析过的内容。
保持简洁（2-3 句话）。"""

        try:
            response = self.llm_client.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            # Fallback：直接显示历史
            if self.analysis_history:
                last = self.analysis_history[-1]
                return f"你刚才问了「{last['query']}」，我分析了 {', '.join(last['symbols'])}。"
            return "我们还没有进行过任何分析对话。"

    def handle_news_query(self, query: str) -> str:
        """处理新闻查询（使用 Google News RSS）"""

        # 从查询中提取可能的符号
        symbols_to_try = []

        # 常见加密货币符号
        crypto_keywords = {
            'BTC': ['btc', 'bitcoin', '比特幣'],
            'ETH': ['eth', 'ethereum', '以太坊'],
            'SOL': ['sol', 'solana'],
            'PI': ['pi', 'pi network', 'pi幣'],
            'DOGE': ['doge', 'dogecoin'],
            'XRP': ['xrp', 'ripple'],
            'BNB': ['bnb', 'binance'],
        }

        query_lower = query.lower()
        for symbol, keywords in crypto_keywords.items():
            if any(kw in query_lower for kw in keywords):
                symbols_to_try.append(symbol)
                break

        # 如果没有特定符号，尝试从上下文获取
        if not symbols_to_try:
            ctx = self.memory.get_or_create(self.session_id)
            if ctx.symbols_mentioned:
                symbols_to_try = [ctx.symbols_mentioned[-1]]

        # 如果还是没有，使用通用搜索
        if not symbols_to_try:
            symbols_to_try = ['crypto']  # 通用加密货币新闻

        output = []
        output.append(f"\n📰 新闻查询")
        output.append("─" * 40)

        for symbol in symbols_to_try[:2]:  # 最多查 2 个符号
            output.append(f"\n🔍 {symbol} 相关新闻：\n")

            try:
                # 使用 Google News RSS
                news_list = get_crypto_news_google(symbol, limit=5)

                if news_list:
                    for i, news in enumerate(news_list, 1):
                        title = news.get('title', 'No Title')
                        source = news.get('source', 'Unknown')
                        url = news.get('url', '')
                        pub_date = news.get('published_at', '')

                        # 格式化日期
                        if pub_date and pub_date != 'N/A':
                            try:
                                from email.utils import parsedate_to_datetime
                                dt = parsedate_to_datetime(pub_date)
                                pub_date = dt.strftime('%m/%d %H:%M')
                            except:
                                pub_date = pub_date[:16] if len(pub_date) > 16 else pub_date

                        output.append(f"  {i}. {title}")
                        output.append(f"     📅 {pub_date} | 📎 {source}")
                        if url:
                            output.append(f"     🔗 {url[:60]}...")
                        output.append("")
                else:
                    output.append(f"  ⚠️ 无法获取 {symbol} 的新闻，请稍后再试")
                    output.append("")

            except Exception as e:
                output.append(f"  ❌ 新闻获取失败: {str(e)}")
                output.append("")

        return "\n".join(output)

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

        # 记录用户消息
        self._add_message("user", query)

        # 处理指令
        if query.startswith("/"):
            result = self.handle_command(query)
            self._add_message("assistant", result)
            return result

        # 检查是否有待处理的审核
        if self.pending_review:
            result = self.handle_review_response(query)
            self._add_message("assistant", result)
            return result

        # 使用意图分类决定如何处理
        intent = self.classify_intent(query)

        if intent == "greeting":
            result = self.handle_general_chat(query, intent)
        elif intent == "general_chat":
            result = self.handle_general_chat(query, intent)
        elif intent == "news_query":
            result = self.handle_news_query(query)
        elif intent == "follow_up":
            result = self.handle_follow_up(query)
        elif intent == "memory_query":
            result = self.handle_memory_query(query)
        elif intent == "crypto_analysis":
            result = self.analyze(query)
        else:
            # 默认作为一般对话处理
            result = self.handle_general_chat(query, intent)

        # 记录助手回复
        self._add_message("assistant", result)
        return result

    def _add_message(self, role: str, content: str):
        """添加消息到历史"""
        # 过滤掉一些不需要记录的内容
        if content == "QUIT" or content == "" or content.startswith("\033["):
            return

        self.message_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        # 保持最近 50 条消息
        if len(self.message_history) > 50:
            self.message_history = self.message_history[-50:]

        # 更新 ConversationMemory
        ctx = self.memory.get_or_create(self.session_id)
        self.memory.update_with_query(ctx, content if role == "user" else "")

    def handle_unknown(self, query: str) -> str:
        """处理无法识别的输入（使用 LLM）"""
        prompt = f"""用戶輸入：{query}

你無法理解這個輸入的意圖。請用繁體中文友善地：
1. 說明你不確定這個請求
2. 提示用戶可以問加密貨幣相關問題
3. 保持簡短（2-3 句話）"""

        try:
            response = self.llm_client.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception:
            return f"🤔 我不確定「{query}」是什麼意思。\n試試問我加密貨幣問題，如「分析 BTC」"

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
