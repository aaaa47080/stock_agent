"""
Admin Agent - 任務分析、路由和協調中樞

Admin Agent 負責：
1. 分析用戶意圖和任務複雜度
2. 從 Agent Registry 中選擇適當的 Agent
3. 對於複雜任務，協調 Planning Manager 和多個 Agent 的執行
4. 聚合結果返回給用戶
"""
import json
import re
from typing import List, Dict, Generator, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field

from core.agent_registry import agent_registry, AgentConfig


# ============================================================================
# 數據模型
# ============================================================================

class TaskAnalysis(BaseModel):
    """任務分析結果"""
    is_complex: bool = Field(..., description="是否為複雜任務")
    complexity_reason: str = Field(default="", description="複雜度判斷原因")
    assigned_agent: str = Field(..., description="指派的 Agent ID")
    execution_mode: str = Field(default="auto", description="執行模式: planning, deep_analysis, simple")
    confidence: float = Field(default=0.8, ge=0, le=1, description="分析置信度")
    original_question: str = Field(default="", description="用戶原始問題")
    symbols: List[str] = Field(default_factory=list, description="涉及的幣種符號")


class SubTask(BaseModel):
    """子任務定義"""
    id: str = Field(..., description="子任務唯一 ID")
    description: str = Field(..., description="任務描述")
    assigned_agent: str = Field(..., description="指派的 Agent ID")
    tools_hint: List[str] = Field(default_factory=list, description="建議使用的工具")
    dependencies: List[str] = Field(default_factory=list, description="依賴的其他子任務 ID")
    status: str = Field(default="pending", description="任務狀態")
    result: Optional[str] = Field(default=None, description="任務執行結果")
    symbol: Optional[str] = Field(default=None, description="相關的加密貨幣符號")


# ============================================================================
# Admin Agent 主類
# ============================================================================

class AdminAgent:
    """
    Admin Agent - 任務分派和協調中樞

    使用方式:
        admin = AdminAgent(user_llm_client, user_provider)
        task = admin.analyze_task("BTC 現在多少錢？")

        if task.is_complex:
            for chunk in admin.route_complex_task(message, task):
                yield chunk
        else:
            for chunk in admin.route_simple_task(task):
                yield chunk
    """

    def __init__(
        self,
        user_llm_client=None,
        user_provider: str = "openai",
        verbose: bool = False,
        user_model: str = None
    ):
        """
        初始化 Admin Agent

        Args:
            user_llm_client: 用戶提供的 LLM Client
            user_provider: LLM Provider (openai, openrouter, google_gemini)
            verbose: 是否顯示詳細日誌
            user_model: 用戶選擇的模型名稱
        """
        self.user_llm_client = user_llm_client
        self.user_provider = user_provider
        self.user_model = user_model
        self.verbose = verbose

        # 延遲導入 PlanningManager 避免循環依賴
        self._planning_manager = None

    @property
    def planning_manager(self):
        """延遲加載 Planning Manager"""
        if self._planning_manager is None:
            from core.planning_manager import PlanningManager
            self._planning_manager = PlanningManager(
                self.user_llm_client,
                self.user_provider,
                self.user_model
            )
        return self._planning_manager

    def _get_model_for_provider(self) -> str:
        """根據 provider 獲取適合的模型名稱"""
        try:
            from core.model_config import get_default_model
            if self.user_provider == "google_gemini":
                return get_default_model("google_gemini")
            elif self.user_provider == "openrouter":
                return get_default_model("openrouter")
            else:
                return get_default_model("openai")
        except ImportError:
            # 如果配置文件不可用，使用默認值
            if self.user_provider == "google_gemini":
                return "gemini-3-flash-preview"
            elif self.user_provider == "openrouter":
                return "gpt-4o-mini"
            else:
                return "gpt-4o-mini"

    def analyze_task(self, user_message: str) -> TaskAnalysis:
        """
        使用 LLM 分析任務複雜度和適合的 Agent

        Args:
            user_message: 用戶輸入的消息

        Returns:
            TaskAnalysis 對象
        """
        # 如果沒有 LLM client，使用 fallback 方法
        if not self.user_llm_client:
            return self._fallback_analyze(user_message)

        # 構建 Agent 描述
        agent_descriptions = agent_registry.get_agent_description_for_llm()
        enabled_agents = list(agent_registry.get_enabled_agents().keys())

        system_prompt = f"""你是一個智能任務分析器 (Admin Agent)。你的任務是：
        1. 分析用戶的問題
        2. 判斷任務的複雜度（簡單/複雜）
        3. 決定最佳的執行模式 (Execution Mode)
        4. 選擇最適合處理該任務的 Agent
        5. 從用戶查詢中精確提取加密貨幣符號

        ## 可用的 Agent 列表：
        {agent_descriptions}

        ## 執行模式 (execution_mode) 選擇指南：

        1. **planning** (規劃模式):
        - 適用於：包含多個不相關的子問題（例如「問名字 + 查價格」）。
        - 適用於：涉及多個不同幣種的比較或分析（例如「比較 BTC 和 ETH」）。
        - 適用於：任務需要被拆解為多個步驟才能完成。

        2. **deep_analysis** (深度分析模式):
        - 適用於：針對**單一幣種**進行深入的全方位投資分析。
        - 關鍵詞：「深度分析」、「完整報告」、「值得買嗎」、「交易策略」。
        - 注意：如果包含多個幣種，請選 planning。

        3. **simple** (簡單模式):
        - 適用於：單一、明確的數據查詢或閒聊。
        - 例如：「BTC 價格」、「你好」、「RSI 是多少」。

        ## 加密貨幣符號提取指南：
        - 精確識別加密貨幣符號，如 BTC, ETH, SOL, XRP, ADA, DOGE, DOT, AVAX, LTC, LINK, UNI, BCH, SHIB 等
        - 支援中英文混合文本，例如 "BTC現在值得購買嘛" 應提取 ["BTC"]
        - 避免誤識別常見詞語，如 USD, THE, AND, FOR 等
        - 符號前後可能有中文、英文、數字或特殊字符
        - 仔細區分相似詞語，如 "buy" 不是幣種，但 "BTC" 是

        ## 決策原則：
        1. **數據優先**：只要用戶的問題中包含加密貨幣（如 BTC, ETH, PI），`assigned_agent` 絕對不能是 `admin_chat_agent`。必須選擇能處理數據的 Agent。
        2. **混合即規劃**：如果一個句子包含兩個或以上的意圖（例如：1.問候 + 2.查價），這被定義為「混合意圖」，必須設定 `execution_mode: "planning"` 且 `is_complex: true`。

        ## 範例：

        用戶: "你好，BTC 現在多少錢？"
        JSON:
        {{
            "is_complex": true,
            "complexity_reason": "包含問候與特定幣種價格查詢，屬於混合意圖任務",
            "execution_mode": "planning",
            "assigned_agent": "shallow_crypto_agent",
            "symbols": ["BTC"],
            "confidence": 1.0
        }}

        用戶: "比較 BTC 和 ETH 目前的 RSI"
        JSON:
        {{
            "is_complex": true,
            "complexity_reason": "涉及多個幣種的對比分析",
            "execution_mode": "planning",
            "assigned_agent": "shallow_crypto_agent",
            "symbols": ["BTC", "ETH"],
            "confidence": 1.0
        }}

        用戶: "BTC 值得買嗎？"
        JSON:
        {{
            "is_complex": true,
            "complexity_reason": "需要深入的投資建議與策略評估",
            "execution_mode": "deep_analysis",
            "assigned_agent": "deep_crypto_agent",
            "symbols": ["BTC"],
            "confidence": 0.95
        }}

        用戶: "BTC現在值得購買嘛"
        JSON:
        {{
            "is_complex": true,
            "complexity_reason": "需要深入的投資建議與策略評估",
            "execution_mode": "deep_analysis",
            "assigned_agent": "deep_crypto_agent",
            "symbols": ["BTC"],
            "confidence": 0.95
        }}

        用戶: "哈囉"
        JSON:
        {{
            "is_complex": false,
            "complexity_reason": "純粹的社交問候",
            "execution_mode": "simple",
            "assigned_agent": "admin_chat_agent",
            "symbols": [],
            "confidence": 1.0
        }}

        ## 輸出格式（JSON）：

        {{
            "is_complex": true/false,
            "complexity_reason": "判斷原因",
            "execution_mode": "planning" | "deep_analysis" | "simple",
            "assigned_agent": "agent_id (必須是: {', '.join(enabled_agents)})",
            "symbols": ["BTC", "ETH"], // 提取到的幣種符號列表
            "confidence": 0.9  // 0-1 之間
        }}
        """

        try:
            response = self.user_llm_client.chat.completions.create(
                model=self._get_model_for_provider(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                response_format={"type": "json_object"} if self.user_provider != "google_gemini" else None
            )

            result_text = response.choices[0].message.content

            # 嘗試解析 JSON
            try:
                # 處理可能包含 markdown 代碼塊的情況
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]

                result = json.loads(result_text)

                # 驗證 assigned_agent 是有效的
                if result.get("assigned_agent") not in enabled_agents:
                    result["assigned_agent"] = self._fallback_agent_selection(user_message)

                return TaskAnalysis(
                    is_complex=result.get("is_complex", False),
                    complexity_reason=result.get("complexity_reason", ""),
                    assigned_agent=result.get("assigned_agent", "admin_chat_agent"),
                    execution_mode=result.get("execution_mode", "simple"),
                    symbols=result.get("symbols", []),
                    confidence=result.get("confidence", 0.8),
                    original_question=user_message
                )

            except json.JSONDecodeError:
                if self.verbose:
                    print(f"[AdminAgent] JSON parse error, using fallback. Response: {result_text[:200]}")
                return self._fallback_analyze(user_message)

        except Exception as e:
            if self.verbose:
                print(f"[AdminAgent] LLM error: {e}")
            return self._fallback_analyze(user_message)

    def _fallback_analyze(self, user_message: str) -> TaskAnalysis:
        """
        當 LLM 分析失敗時的降級方案

        使用關鍵詞匹配進行基礎路由
        """
        message_lower = user_message.lower()
        symbols = self._extract_symbols(user_message)

        # 1. 檢查是否需要深度分析
        deep_keywords = [
            "投資", "買", "賣", "做多", "做空", "long", "short",
            "建議", "策略", "值得", "應該", "可以買", "能買",
            "深度分析", "完整分析", "詳細分析", "風險"
        ]
        is_deep = any(k in message_lower for k in deep_keywords)

        if is_deep and symbols:
            return TaskAnalysis(
                is_complex=True,
                complexity_reason="包含投資決策相關關鍵詞",
                assigned_agent="deep_crypto_agent",
                execution_mode="deep_analysis",
                symbols=symbols,
                confidence=0.7,
                original_question=user_message
            )

        # 2. 檢查是否為淺層加密貨幣查詢
        shallow_keywords = [
            "價格", "多少錢", "現價", "rsi", "macd", "指標",
            "新聞", "消息", "漲", "跌", "成交量"
        ]
        is_shallow = any(k in message_lower for k in shallow_keywords) or symbols

        if is_shallow:
            return TaskAnalysis(
                is_complex=False,
                complexity_reason="簡單數據查詢",
                assigned_agent="shallow_crypto_agent",
                execution_mode="simple",
                symbols=symbols,
                confidence=0.7,
                original_question=user_message
            )

        # 3. 預設為行政 Agent
        return TaskAnalysis(
            is_complex=False,
            complexity_reason="一般性問題",
            assigned_agent="admin_chat_agent",
            execution_mode="simple",
            symbols=[],
            confidence=0.6,
            original_question=user_message
        )

    def _fallback_agent_selection(self, user_message: str) -> str:
        """
        當 LLM 無法判斷時的降級選擇

        邏輯：有加密貨幣符號 → shallow_crypto_agent，否則 → admin_chat_agent
        """
        symbols = self._extract_symbols(user_message)
        if symbols:
            return "shallow_crypto_agent"
        return "admin_chat_agent"

    def _extract_symbols(self, text: str) -> List[str]:
        """從文本中提取加密貨幣符號"""
        # 擴展幣種列表，包含更多熱門幣種
        crypto_symbols = [
            # Major coins
            'BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX', 'LTC', 'LINK', 'UNI', 'BCH', 'SHIB', 'ETC', 'TRX', 'MATIC', 'XLM', 'ATOM', 'NEAR', 'APT', 'AR', 'PI', 'TON',
            # Altcoins
            'BNB', 'SUI', 'STX', 'FLOW', 'HBAR', 'VET', 'ALGO', 'XTZ', 'EOS', 'XMR', 'ZEC', 'ZIL', 'ONT', 'THETA', 'AAVE', 'SAND', 'MANA', 'PEPE', 'FLOKI', 'MEME', 'WIF', 'BONK',
            'RENDER', 'TAO', 'SEI', 'JUP', 'PYTH', 'STRK', 'WLD', 'ORDI', 'INJ', 'TIA', 'DYM', 'FIL', 'ICP', 'SGB', 'XDC', 'IOTX', 'KDA', 'QLC', 'XVG', 'LSK', 'STEEM', 'HIVE',
            'WAVES', 'DGB', 'SC', 'RVN', 'DCR', 'SYS', 'UBQ', 'XEM', 'FTM', 'CRV', 'MKR', 'COMP', 'BAL', 'YFI', 'SNX', 'REN', 'KNC', 'BAND', 'RLC', 'UMA', 'SRM', 'OCEAN', 'CVC',
            'ANKR', 'OGN', 'CTSI', 'BNT', 'WRX', 'STORJ', 'ZRX', 'BAL', 'RLC', 'OCEAN', 'CVC', 'ANKR', 'OGN', 'CTSI', 'BAND', 'WRX', 'STORJ', 'ILV', 'YGG', 'IMX', 'DYDX', 'GMX',
            'SPELL', 'UST', 'LUNA', 'FIL', 'HBAR', 'VET', 'IOTA', 'CKB', 'RVN', 'ALGO', 'QTUM', 'ONT', 'ZEC', 'DASH', 'ZEN', 'DCR', 'BAT', 'REP', 'LINK', 'COMP', 'SNX', 'MKR', 'YFI',
            'CRV', 'UMA', 'UNI', 'SUSHI', 'BCH', 'LTC', 'XMR', 'ADA', 'DOT', 'DOGE', 'ATOM', 'BCH', 'XRP', 'ETC', 'TRX', 'EOS', 'XLM', 'BSV', 'NEO', 'HT', 'OKB', 'LEO', 'FTT', 'APT',
            'GMT', 'SAND', 'MANA', 'AXS', 'ILV', 'RLC', 'YGG', 'IMX', 'DYDX', 'GMX', 'SPELL', 'UST', 'LUNA', 'FIL', 'HBAR', 'VET', 'IOTA', 'CKB', 'RVN', 'ALGO', 'QTUM', 'ONT', 'ZEC',
            'DASH', 'ZEN', 'DCR', 'BAT', 'REP', 'FIL', 'LINK', 'COMP', 'SNX', 'MKR', 'YFI', 'CRV', 'UMA', 'UNI', 'SUSHI', 'BCH', 'LTC', 'XMR', 'ADA', 'DOT', 'DOGE', 'ATOM', 'BCH',
            'XRP', 'ETC', 'TRX', 'EOS', 'XLM', 'BSV', 'NEO', 'HT', 'OKB', 'LEO', 'FTT', 'APT', 'GMT', 'SGB', 'XDC', 'IOTX', 'KDA', 'QLC', 'ADA', 'XVG', 'LSK', 'STEEM', 'HIVE',
            'WAVES', 'XTZ', 'DGB', 'SC', 'ZIL', 'RVN', 'DCR', 'SYS', 'UBQ', 'XEM', 'LSK', 'STEEM', 'HIVE', 'WAVES', 'XTZ', 'DGB', 'SC', 'ZIL', 'RVN', 'DCR', 'SYS', 'UBQ', 'XEM',
            'FLOW', 'ICP', 'SOL', 'AVAX', 'FTM', 'NEAR', 'AAVE', 'CRV', 'MKR', 'COMP', 'BAL', 'YFI', 'SNX', 'REN', 'KNC', 'BAND', 'RLC', 'UMA', 'SRM', 'OCEAN', 'CVC', 'ANKR', 'OGN',
            'CTSI', 'BNT', 'WRX', 'STORJ', 'ZRX', 'BAL', 'RLC', 'OCEAN', 'CVC', 'ANKR', 'OGN', 'CTSI', 'BAND', 'WRX', 'STORJ'
        ]

        # 使用工具提取加密貨幣符號（保留原有方法作為備用）
        try:
            from core.tools import extract_crypto_symbols_tool
            result = extract_crypto_symbols_tool(text)
            return result.get("extracted_symbols", [])
        except:
            # 如果工具不可用，使用原有的正則表達式方法
            escaped_symbols = [re.escape(symbol) for symbol in crypto_symbols]
            pattern = r'(?<![a-zA-Z0-9])(' + '|'.join(escaped_symbols) + r')(?![a-zA-Z0-9])'
            matches = re.findall(pattern, text.upper(), re.IGNORECASE)

            # 去重並過濾常見非幣種詞
            common_words = {'USDT', 'BUSD', 'USD', 'THE', 'AND', 'FOR', 'ARE', 'CAN', 'SEE', 'DID', 'HAS', 'WAS', 'NOT', 'BUT', 'ALL', 'ANY', 'NEW', 'NOW', 'ONE', 'TWO', 'BUY', 'SELL', 'PAY', 'GET', 'RUN', 'SET', 'TOP', 'LOW', 'KEY', 'USE', 'TRY', 'BIG', 'OLD', 'BAD', 'HOT', 'RED', 'BIT', 'EAT', 'FLY', 'MAN', 'BOY', 'ART', 'CAR', 'DAY', 'WAY', 'HEY', 'WHY', 'HOW', 'WHO'}
            return list(set(m for m in matches if m not in common_words))

    def route_simple_task(
        self,
        task: TaskAnalysis,
        user_message: str,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        處理簡單任務 - 直接路由到單一 Agent

        Args:
            task: 任務分析結果
            user_message: 原始用戶消息
            **kwargs: 傳遞給 Agent 的額外參數

        Yields:
            Agent 的回應片段
        """
        agent_config = agent_registry.get_agent(task.assigned_agent)

        if not agent_config:
            yield f"錯誤：找不到 Agent '{task.assigned_agent}'"
            return

        if self.verbose:
            print(f"[AdminAgent] Routing to {task.assigned_agent} ({agent_config.name})")

        # 根據 Agent 類型創建對應的執行器
        if task.assigned_agent == "deep_crypto_agent" and agent_config.use_debate_system:
            # 深度分析走完整流程
            yield from self._execute_deep_analysis(task, user_message, **kwargs)
        elif task.assigned_agent == "shallow_crypto_agent":
            # 淺層分析使用 CryptoAgent with tools
            yield from self._execute_shallow_analysis(task, user_message, **kwargs)
        else:
            # 行政或其他 Agent 使用簡單對話
            yield from self._execute_chat(task, user_message, **kwargs)

    def route_complex_task(
        self,
        user_message: str,
        task: TaskAnalysis,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        處理複雜任務 - 交給 Planning Manager 拆分後並行執行

        Args:
            user_message: 原始用戶消息
            task: 任務分析結果
            **kwargs: 額外參數

        Yields:
            處理過程和結果
        """
        yield "[PROCESS_START]\n"
        yield f"[PROCESS] 🧠 Admin Agent 判定這是一個複雜任務\n"
        yield f"[PROCESS] 📋 原因: {task.complexity_reason}\n"
        yield f"[PROCESS] ⚙️ 執行模式: {task.execution_mode}\n"

        # 根據 execution_mode 進行路由 (不再依賴硬編碼規則)
        if task.execution_mode == "planning":
            # 規劃模式：多幣種或混合意圖
            yield f"[PROCESS] 🔀 啟動動態規劃路徑...\n"
            yield from self._execute_multi_symbol_analysis(task, user_message, **kwargs)
        elif task.execution_mode == "deep_analysis":
            # 深度分析模式：單幣種深度研究
            yield f"[PROCESS] 🎯 啟動單幣種深度分析...\n"
            yield from self._execute_deep_analysis(task, user_message, **kwargs)
        else:
            # Fallback (雖然 route_complex_task 通常是 is_complex=True，但以防萬一)
            yield f"[PROCESS] ⚠️ 未知模式，嘗試使用規劃路徑...\n"
            yield from self._execute_multi_symbol_analysis(task, user_message, **kwargs)

    def _execute_shallow_analysis(
        self,
        task: TaskAnalysis,
        user_message: str,
        **kwargs
    ) -> Generator[str, None, None]:
        """執行淺層分析（使用帶工具的 CryptoAgent）"""
        try:
            from core.agents import CryptoAgent

            # 創建臨時 Agent
            agent = CryptoAgent(
                user_api_key=kwargs.get("user_api_key"),
                user_provider=self.user_provider,
                user_client=self.user_llm_client,
                verbose=self.verbose
            )

            # 執行並 yield 結果
            for chunk in agent.chat_stream(user_message):
                yield chunk

        except Exception as e:
            yield f"執行淺層分析時發生錯誤: {str(e)}"

    def _execute_deep_analysis(
        self,
        task: TaskAnalysis,
        user_message: str,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        執行深度分析（使用完整的 LangGraph 會議討論流程）

        這會調用現有的 app.stream() 流程
        """
        from core.graph import app
        from core.config import DEFAULT_KLINES_LIMIT

        # 優先使用 TaskAnalysis 中的 symbols
        symbol = None
        if task.symbols and len(task.symbols) > 0:
            symbol = task.symbols[0]

        # 如果沒有，嘗試本地提取
        if not symbol:
            extracted_symbols = self._extract_symbols(user_message)
            symbol = extracted_symbols[0] if extracted_symbols else None

        if not symbol:
            yield "錯誤：深度分析需要指定加密貨幣符號。請告訴我您想分析哪個幣種？"
            return

        yield "[PROCESS_START]\n"
        yield f"[PROCESS] 🚀 正在啟動深度研究 Agent，分析 {symbol}...\n"

        # 查找交易所
        try:
            exchange_info = self._find_available_exchange(symbol)
            if not exchange_info:
                yield f"[PROCESS] ❌ 找不到 {symbol} 的交易對\n"
                yield "[PROCESS_END]\n"
                return

            exchange, normalized_symbol = exchange_info
            yield f"[PROCESS] ✅ 找到交易對: {normalized_symbol} @ {exchange}\n"

        except Exception as e:
            yield f"[PROCESS] ❌ 查找交易所時出錯: {str(e)}\n"
            yield "[PROCESS_END]\n"
            return

        # 構建 state_input
        market_type = kwargs.get("market_type", "spot")
        state_input = {
            "symbol": normalized_symbol,
            "exchange": exchange,
            "interval": kwargs.get("interval", "1d"),
            "limit": DEFAULT_KLINES_LIMIT,
            "market_type": market_type,
            "leverage": 1 if market_type == "spot" else 5,
            "include_multi_timeframe": True,
            "short_term_interval": "1h",
            "medium_term_interval": "4h",
            "long_term_interval": "1d",
            "preloaded_data": None,
            "account_balance": kwargs.get("account_balance"),
            "selected_analysts": ["technical", "sentiment", "fundamental", "news"],
            "perform_trading_decision": True,
            "execute_trade": False,
            "debate_round": 0,
            "debate_history": [],
            "user_llm_client": self.user_llm_client,
            "user_provider": self.user_provider
        }

        # 執行分析流程
        try:
            accumulated_state = state_input.copy()

            for event in app.stream(state_input):
                for node_name, state_update in event.items():
                    accumulated_state.update(state_update)

                    # 輸出各節點的進度信息
                    yield from self._format_node_output(node_name, state_update, accumulated_state)

            yield "[PROCESS_END]\n"

            # 最終報告
            yield "[RESULT]\n"
            from core.tools import format_full_analysis_result
            formatted_report = format_full_analysis_result(
                accumulated_state,
                "現貨" if market_type == "spot" else "合約",
                normalized_symbol,
                state_input["interval"]
            )
            yield formatted_report

        except Exception as e:
            import traceback
            if self.verbose:
                traceback.print_exc()
            yield f"[PROCESS] ❌ 分析過程中發生錯誤: {str(e)}\n"
            yield "[PROCESS_END]\n"

    def _execute_multi_symbol_analysis(
        self,
        task: TaskAnalysis,
        user_message: str,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        執行多幣種或複雜並行分析

        Args:
            task: 任務分析結果
            user_message: 原始用戶消息
        """
        # 使用 Planning Manager 智能拆分任務
        yield f"[PROCESS] 🧠 正在調用 Planning Manager 進行任務拆解...\n"
        # 傳遞空列表作為 symbols，讓 Planning Manager 自行從 message 中提取
        plan = self.planning_manager.create_task_plan(user_message, [])
        subtasks = plan.subtasks

        yield f"[PROCESS] 📊 拆解出 {len(subtasks)} 個子任務\n"

        # 列出所有子任務細節
        for st in subtasks:
            agent_name = st.assigned_agent
            yield f"[PROCESS]   📍 [子任務 {st.id}] {st.description} ({agent_name})\n"

        # 並行執行子任務
        results = {}
        # 限制並發數，避免 API Rate Limit
        max_workers = min(4, len(subtasks))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._execute_subtask_sync, subtask, **kwargs): subtask.id
                for subtask in subtasks
            }

            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    result = future.result()
                    results[task_id] = result

                    # 找到對應的子任務以獲取描述
                    st = next((s for s in subtasks if s.id == task_id), None)
                    desc = st.description if st else task_id

                    yield f"[PROCESS] ✅ 完成子任務: {desc}\n"
                except Exception as e:
                    results[task_id] = f"錯誤: {str(e)}"
                    yield f"[PROCESS] ❌ 子任務 {task_id} 失敗: {str(e)}\n"

        yield "[PROCESS_END]\n"

        # 聚合結果
        yield "[RESULT]\n"

        # 3. 最終合成 (Synthesis) - 將所有結果彙整為一個完整的回答
        yield f"[PROCESS] 🧠 正在彙整 {len(results)} 個子任務的結果...\n"

        synthesis_prompt = f"""你是一個高級金融分析助手。用戶問了一個複雜的問題，我們已經將其拆解為多個子任務並執行完畢。
現在請根據「用戶原始問題」和「子任務執行結果」，生成一個完整、流暢、邏輯連貫的最終回答。

## 用戶原始問題：
{user_message}

## 子任務執行結果：
"""
        for task_id, result in results.items():
            # 找到對應的子任務描述
            desc = next((st.description for st in subtasks if st.id == task_id), "未知任務")
            synthesis_prompt += f"\n--- 子任務: {desc} ---\n{result}\n"

        synthesis_prompt += "\n\n## 你的任務：\n請綜合以上資訊，直接回答用戶的問題。不需要提及「子任務」或「拆解過程」，直接給出最終答案即可。請使用繁體中文。"

        try:
            response = self.user_llm_client.chat.completions.create(
                model=self._get_model_for_provider(),
                messages=[
                    {"role": "system", "content": "你是一個專業的整合分析師。"},
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.7
            )
            final_answer = response.choices[0].message.content
            yield final_answer

        except Exception as e:
            yield f"彙整結果時發生錯誤: {str(e)}\n\n以下是原始結果:\n"
            for task_id, result in results.items():
                desc = next((st.description for st in subtasks if st.id == task_id), task_id)
                yield f"### {desc}\n{result}\n\n"

    def _execute_subtask_sync(self, subtask: SubTask, **kwargs) -> str:
        """同步執行子任務（用於並行執行）"""
        try:
            from core.agents import CryptoAgent

            agent = CryptoAgent(
                user_api_key=kwargs.get("user_api_key"),
                user_provider=self.user_provider,
                user_client=self.user_llm_client,
                verbose=self.verbose
            )

            # 構建查詢
            if subtask.symbol:
                query = f"{subtask.symbol} 的價格和技術指標"
            else:
                query = subtask.description

            # 執行並收集結果
            result_parts = []
            for chunk in agent.chat_stream(query):
                result_parts.append(chunk)

            return "".join(result_parts)

        except Exception as e:
            return f"執行失敗: {str(e)}"

    def _execute_chat(
        self,
        task: TaskAnalysis,
        user_message: str,
        **kwargs
    ) -> Generator[str, None, None]:
        """執行簡單對話（支援工具調用）"""
        if not self.user_llm_client:
            yield "抱歉，系統暫時無法處理您的請求。請稍後再試。"
            return

        # 檢查 Agent 是否有配置工具
        agent_config = agent_registry.get_agent(task.assigned_agent)
        agent_tools = agent_config.tools if agent_config else []

        # 如果有工具，使用帶工具的 Agent
        if agent_tools:
            try:
                from core.tools import get_tools_by_names
                from langchain_openai import ChatOpenAI
                from langchain_google_genai import ChatGoogleGenerativeAI
                from langgraph.prebuilt import create_react_agent
                from langchain_core.messages import HumanMessage, AIMessage
                import os

                # 獲取工具
                tools = get_tools_by_names(agent_tools)

                # 創建 LLM
                llm = None
                if self.user_provider == "google_gemini":
                    api_key = kwargs.get("user_api_key") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                    if api_key:
                        model_name = self.user_model or "gemini-2.0-flash"
                        llm = ChatGoogleGenerativeAI(
                            model=model_name,
                            temperature=0.7,
                            google_api_key=api_key
                        )
                else:
                    # OpenAI 或 OpenRouter
                    api_key = kwargs.get("user_api_key") or os.getenv("OPENAI_API_KEY")
                    base_url = None
                    if self.user_provider == "openrouter":
                        base_url = "https://openrouter.ai/api/v1"
                    if api_key:
                        model_name = self.user_model or self._get_model_for_provider()
                        llm = ChatOpenAI(
                            model=model_name,
                            temperature=0.7,
                            api_key=api_key,
                            base_url=base_url
                        )

                if llm and tools:
                    # 創建 ReAct Agent
                    system_prompt = """你是一個友善的加密貨幣分析助手。
你可以幫助用戶了解加密貨幣市場、回答問題、提供使用說明。
你有權限使用工具來查詢當前時間等資訊。
請用繁體中文回答。"""

                    agent = create_react_agent(llm, tools, prompt=system_prompt)
                    result = agent.invoke({"messages": [HumanMessage(content=user_message)]})

                    # 提取 AI 回應
                    if "messages" in result:
                        for msg in reversed(result["messages"]):
                            if isinstance(msg, AIMessage) and msg.content:
                                content = msg.content
                                if isinstance(content, list):
                                    text_parts = [p if isinstance(p, str) else p.get('text', '') for p in content]
                                    yield ''.join(text_parts)
                                else:
                                    yield str(content)
                                return

            except Exception as e:
                if self.verbose:
                    print(f"[AdminAgent] Tool-based chat failed: {e}, falling back to simple chat")
                # 繼續使用無工具對話作為 fallback

        # 無工具或工具執行失敗時，使用純對話模式
        try:
            system_prompt = """你是一個友善的加密貨幣分析助手。
你可以幫助用戶了解加密貨幣市場、回答問題、提供使用說明。
對於投資建議，請提醒用戶這只是參考意見，不構成投資建議。
請用繁體中文回答。"""

            response = self.user_llm_client.chat.completions.create(
                model=self._get_model_for_provider(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )

            yield response.choices[0].message.content

        except Exception as e:
            yield f"處理您的請求時發生錯誤: {str(e)}"

    def _find_available_exchange(self, symbol: str) -> Optional[Tuple[str, str]]:
        """查找可用的交易所和標準化符號"""
        from core.config import SUPPORTED_EXCHANGES
        from data.data_fetcher import get_data_fetcher

        for exchange in SUPPORTED_EXCHANGES:
            try:
                normalized = self._normalize_symbol(symbol, exchange)
                fetcher = get_data_fetcher(exchange)
                test_data = fetcher.get_historical_klines(normalized, "1d", limit=1)
                if test_data is not None and not test_data.empty:
                    return (exchange, normalized)
            except:
                continue
        return None

    def _normalize_symbol(self, symbol: str, exchange: str) -> str:
        """標準化符號格式"""
        symbol = symbol.upper().strip()
        base = symbol.replace("-", "").replace("_", "")

        if base.endswith("USDT"):
            base = base[:-4]
        elif base.endswith("USD"):
            base = base[:-3]

        if exchange.lower() == "okx":
            return f"{base}-USDT"
        else:
            return f"{base}USDT"

    def _format_node_output(
        self,
        node_name: str,
        state_update: Dict,
        accumulated_state: Dict
    ) -> Generator[str, None, None]:
        """格式化 LangGraph 節點的輸出"""

        if node_name == "prepare_data":
            price = state_update.get("current_price", 0)
            yield f"[PROCESS] ✅ 數據準備完成: 當前價格 ${price:.4f}\n"

        elif node_name == "run_analyst_team":
            reports = state_update.get("analyst_reports", [])
            yield f"[PROCESS] 📊 AI 分析師團隊: 完成 {len(reports)} 份報告\n"
            for report in reports:
                analyst_type = getattr(report, 'analyst_type', '分析師')
                bullish = len(getattr(report, 'bullish_points', []))
                bearish = len(getattr(report, 'bearish_points', []))
                total = bullish + bearish
                if total > 0:
                    bull_ratio = bullish / total
                    bull_bars = round(bull_ratio * 5)
                    bear_bars = 5 - bull_bars
                    bar = '🟩' * bull_bars + '🟥' * bear_bars
                    yield f"[PROCESS]   → {analyst_type}: {bar} ({bullish}多/{bearish}空)\n"

        elif node_name == "run_research_debate":
            history = accumulated_state.get("debate_history", [])
            if history:
                latest = history[-1]
                yield f"[PROCESS] ⚔️ 第 {latest.get('round')} 輪辯論完成\n"

        elif node_name == "run_debate_judgment":
            judgment = state_update.get("debate_judgment")
            if judgment:
                yield f"[PROCESS] 👨‍⚖️ 辯論裁決: 勝方 {judgment.winning_stance} → 建議 {judgment.suggested_action}\n"

        elif node_name == "run_trader_decision":
            decision = state_update.get("trader_decision")
            if decision:
                follows = "✅ 遵循裁判" if decision.follows_judge else "⚠️ 偏離裁判"
                yield f"[PROCESS] ⚖️ 交易員決策: {decision.decision} | 倉位 {decision.position_size:.0%} | {follows}\n"

        elif node_name == "run_risk_management":
            risk = state_update.get("risk_assessment")
            if risk:
                status = "✅ 通過" if risk.approve else "❌ 不通過"
                yield f"[PROCESS] 🛡️ 風險評估: {risk.risk_level} ({status})\n"

        elif node_name == "run_fund_manager_approval":
            approval = state_update.get("final_approval")
            if approval:
                yield f"[PROCESS] 💰 基金經理審批: {approval.final_decision}\n"
