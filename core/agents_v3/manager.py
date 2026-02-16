"""
Agent V3 Manager Agent

負責任務分解、調度和整合的核心管理 Agent
"""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from .base import SubAgent
from .models import (
    Task, SubTask, AgentResult, Action, TaskType,
    AgentState, ConversationContext, HITLTriggerType
)
from .tool_registry import ToolRegistry
from .hitl import EnhancedHITLManager
from .memory import ConversationMemory
from .codebook import Codebook


class ManagerAgent:
    """
    管理 Agent - 負責任務分解、調度和整合

    職責：
    1. 理解使用者意圖
    2. 檢查 Codebook 是否有相似經驗
    3. 制定執行計畫 (Planning)
    4. 與使用者確認計畫 (HITL Confirm)
    5. 調度 Sub-agents 執行 (Execution)
    6. 整合最終報告
    7. 學習並存入 Codebook
    """

    INTENT_ANALYSIS_PROMPT = """你是一個加密貨幣分析系統的管理者。
你的任務是分析使用者的查詢，判斷需要調度哪些專業 Agent 來處理。

重要：這個系統只能處理以下能力：
- 加密貨幣相關問題（價格、新聞、技術分析）
- 一般對話和問候
- 系統功能介紹
- 對之前回答的追問或反饋

系統無法處理：
- 天氣查詢、訂票訂房、網購或支付
- 其他與加密貨幣無關的功能

使用者查詢：{query}

對話歷史：
{history}

可用的 Agent：
{agents_info}

請分析這個查詢：
1. 判斷主要意圖類型
2. 決定需要調度哪些 Agent
3. 提取相關的加密貨幣符號
4. 判斷是否超出系統能力範圍

以 JSON 格式回覆：
{{
    "intent": "news|technical|chat|deep_analysis|unknown",
    "symbols": ["BTC", "ETH", ...],
    "agents_to_dispatch": ["news", "technical", ...],
    "out_of_scope": true/false,
    "need_more_info": true/false,
    "clarification_question": "如果需要更多資訊，問什麼問題",
    "reasoning": "簡短的判斷理由"
}}
"""

    PLANNING_PROMPT = """你是一個專業的任務規劃師。
目標：為使用者的查詢制定一個執行計畫。

原則：
1. 對於複雜的分析請求，請制定詳細的多步驟計畫。
2. 對於**簡單的資訊查詢**：
   - **價格查詢**：務必使用 `technical` Agent 和 `price_data` 或 `get_crypto_price` 工具。
   - **新聞查詢**：務必使用 `news` Agent。
   - 不要過度規劃，單一步驟即可。

使用者查詢：{query}
意圖：{intent}
相關符號：{symbols}

可用的 Sub-Agents：
{agents_info}

可用的工具 (Tools)：
{tools_info}

請制定一個步驟明確的執行計畫。計畫應該包含一系列的子任務 (SubTasks)。
每個子任務都應該指定由哪個 Agent 執行，以及大概做什麼。

以 JSON 格式回覆：
{{
    "plan": [
        {{
            "step": 1,
            "description": "具體做什麼（例如：獲取 BTC 過去 7 天的價格數據）",
            "agent": "technical",
            "tool_hint": "price_data"
        }},
        {{
            "step": 2,
            "description": "做什麼...",
            "agent": "news",
            "tool_hint": "google_news"
        }}
    ],
    "reasoning": "為什麼這樣規劃"
}}
"""

    DISPATCH_PROMPT = """根據當前計畫和狀態，決定下一步行動。

當前計畫：
{plan}

執行進度：
{progress}

觀察記錄：
{observations}

請決定：
1. 執行下一個未完成的步驟？
2. 如果所有步驟都完成了，是否需要額外補充？
3. 是否已經可以生成最終報告？

以 JSON 格式回覆：
{{
    "action": "dispatch|finish",
    "step_index": 0,  (如果要執行步驟，這是 plan 中的 index)
    "agent_to_dispatch": "agent 名稱",
    "task_description": "給 agent 的具體指令",
    "final_report": "最終報告（如果 action 是 finish）",
    "reasoning": "決策理由"
}}
"""

    def __init__(
        self,
        llm_client,
        agents: Dict[str, SubAgent],
        tool_registry: ToolRegistry,
        hitl: EnhancedHITLManager
    ):
        self.llm = llm_client
        self.agents = agents
        self.tool_registry = tool_registry
        self.hitl = hitl
        self.memory = ConversationMemory()
        self.codebook = Codebook()  # 初始化 Codebook

        # 會話狀態
        self._session_id = None
        self._current_context: Optional[ConversationContext] = None
        self._current_plan: List[Dict] = []
        self._plan_status: List[str] = [] # 'pending', 'completed', 'failed'
        self._max_iterations = 15

    def process(self, query: str, session_id: str = None) -> str:
        """
        處理使用者查詢的主要入口

        流程：
        1. Intent Analysis
        2. Check Codebook / Generate Plan
        3. HITL Confirm Plan
        4. Execute Plan (Loop)
        5. Generate Report & Save to Codebook
        """
        # 初始化會話
        self._session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._current_context = ConversationContext(
            session_id=self._session_id,
            original_query=query
        )
        self._current_plan = []
        self._plan_status = []

        # 重置 HITL
        if self.hitl:
            self.hitl.reset()

        try:
            # Step 1: 分析意圖
            analysis = self._analyze_intent(query)
            self._current_context.task_type = self._map_intent_to_task_type(analysis.get("intent", "unknown"))
            self._current_context.symbols = analysis.get("symbols", [])

            # 處理 Out of Scope
            if analysis.get("out_of_scope"):
                result = self._dispatch_agent("chat", query)
                return result.message if result.success else "抱歉，無法處理此請求。"

            # 處理資訊不足
            if analysis.get("need_more_info"):
                if self.hitl:
                    response = self.hitl.ask(analysis.get("clarification_question", "請提供更多資訊"))
                    self._current_context.add_user_input(response)
                    query = f"{query}（使用者補充：{response}）"
                    # 重新分析
                    analysis = self._analyze_intent(query)
                    self._current_context.symbols = analysis.get("symbols", [])

            # Step 2: 規劃 (Planning)
            # 先查 Codebook
            # 先查 Codebook
            similar_entry = self.codebook.find_similar(query, intent=analysis.get("intent"))
            plan_source = "new"

            if similar_entry:
                print(f"\n📚 發現相似經驗 (相似度高)，來源: {similar_entry['query']}")
                # 適配計畫 (將舊變數替換為新變數)
                self._current_plan = self._adapt_plan(similar_entry['plan'], similar_entry['query'], query)
                plan_source = "codebook"
            else:
                # 無經驗，重新規劃
                self._current_plan = self._generate_plan(query, analysis)

            self._plan_status = ["pending"] * len(self._current_plan)

            # Step 3: HITL 確認計畫 (Confirm)
            if not self._confirm_plan(query, self._current_plan, plan_source):
                return "已取消任務。"

            # Step 4: 執行計畫 (Execution Loop)
            iteration = 0
            while iteration < self._max_iterations:
                iteration += 1

                # 檢查計畫完成度
                if all(s == "completed" for s in self._plan_status):
                    break

                # 決定下一步
                action = self._decide_next_step()

                if action["action"] == "dispatch":
                    idx = action["step_index"]
                    print(f"\n🚀 執行步驟 {idx+1}: {action['task_description']}")
                    
                    # 調度 Agent
                    result = self._dispatch_agent(
                        action["agent_to_dispatch"],
                        action["task_description"]
                    )
                    self._current_context.add_agent_result(result)
                    
                    if result.success:
                        self._plan_status[idx] = "completed"
                    else:
                        self._plan_status[idx] = "failed"
                        print(f"❌ 步驟 {idx+1} 失敗: {result.message}")
                        # 可選擇是否中斷，這裡暫時繼續嘗試其他步驟

                elif action["action"] == "finish":
                    break
                else:
                    break

            # Step 5: 生成報告 & 學習
            final_report = self._generate_final_report()
            
            # 使用者滿意度 (簡化版：如果執行成功且使用者沒說不好，就當作成功)
            # 在實際系統中，可以在這裡問使用者 "滿意嗎？"
            # 這裡我們先假設如果有成功執行步驟就存入 Codebook
            if any(s == "completed" for s in self._plan_status):
                self.codebook.add_entry(query, self._current_plan, reasoning="Successfully executed plan", intent=analysis.get("intent"))
                print("\n💾 已將此成功案例存入 Codebook")

            return final_report

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"處理過程發生錯誤：{str(e)}"

    def _adapt_plan(self, plan: List[Dict], original_query: str, new_query: str) -> List[Dict]:
        """
        適配計畫：將舊計畫中的特定變數（如幣種）替換為新查詢的上下文
        """
        # 簡單優化：如果查詢完全包含在計畫描述中，直接字串替換
        # 但更穩健的方式是使用 LLM 進行重寫
        
        ADAPT_PROMPT = """你是一個計畫適配助手。
目標：將一個針對「舊查詢」的執行計畫，修改為適用於「新查詢」的計畫。
保持原本的步驟結構、工具選擇和邏輯，但修改描述中的關鍵實體（如加密貨幣名稱）。

舊查詢：{original_query}
新查詢：{new_query}

原計畫：
{plan_json}

請回覆修改後的計畫 (JSON 格式)，結構必須與原計畫完全一致。
"""
        try:
            prompt = ADAPT_PROMPT.format(
                original_query=original_query,
                new_query=new_query,
                plan_json=json.dumps(plan, ensure_ascii=False, indent=2)
            )
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = self._parse_json(response.content)
            
            # 如果解析失敗或結果為空，回退到原計畫
            if not result or not isinstance(result, list):
                # 嘗試查找 key "plan"
                if isinstance(result, dict) and "plan" in result:
                    return result["plan"]
                return plan
                
            return result
        except Exception as e:
            print(f"Plan adaptation failed: {e}")
            return plan

    def _analyze_intent(self, query: str) -> dict:
        """分析使用者意圖"""
        agents_info = "\n".join([f"- {name}: {agent.description}" for name, agent in self.agents.items()])
        history = self._get_conversation_history()
        prompt = self.INTENT_ANALYSIS_PROMPT.format(
            query=query, history=history, agents_info=agents_info
        )
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return self._parse_json(response.content)
        except Exception:
            return {"intent": "unknown", "symbols": [], "out_of_scope": False}

    def _generate_plan(self, query: str, analysis: dict) -> List[Dict]:
        """使用 LLM 生成執行計畫"""
        agents_info = "\n".join([f"- {name}: {agent.description}" for name, agent in self.agents.items()])
        tools_info = "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tool_registry.list_all_tools()])
        
        prompt = self.PLANNING_PROMPT.format(
            query=query,
            intent=analysis.get("intent", "unknown"),
            symbols=", ".join(analysis.get("symbols", [])),
            agents_info=agents_info,
            tools_info=tools_info
        )
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = self._parse_json(response.content)
            return result.get("plan", [])
        except Exception as e:
            print(f"Planning failed: {e}")
            # Fallback simple plan
            return [{"step": 1, "description": query, "agent": "chat", "tool_hint": "llm_chat"}]

    def _confirm_plan(self, query: str, plan: List[Dict], source: str) -> bool:
        """
        向使用者展示計畫並請求確認 (HITL)
        """
        if not self.hitl:
            return True

        # 格式化計畫展示
        plan_str = f"對於您的請求「{query}」，我準備了以下計畫 ({'來自過去經驗' if source == 'codebook' else '新生成的計畫'})：\n"
        for item in plan:
            plan_str += f"  {item['step']}. [{item.get('agent', 'unknown')}] {item['description']}\n"
        
        # Auto-Execution Logic:
        # 如果計畫只有一步，且是由 'news' 或 'technical' 執行的簡單任務，則自動執行
        if len(plan) == 1:
            step = plan[0]
            agent_name = step.get('agent', '')
            # 排除 'chat' agent，因為聊天通常是 fallback，可能需要確認
            if agent_name in ['news', 'technical']:
                print(f"🤖 檢測到單一步驟計畫 ({agent_name})，自動執行...")
                return True

        # 使用 HITL 詢問
        # 注意：這裡我們需要擴充 HITL 來支持這種確認
        # 暫時使用 ask 方法
        response = self.hitl.ask(
            f"{plan_str}\n請問是否執行？(Y/n/修改)",
            question_type=HITLTriggerType.CONFIRMATION,
            options=["執行", "不執行", "修改"]
        )
        
        if response in ["執行", "Y", "y", "yes", "ok", "OK"]:
            return True
        elif response in ["修改"]:
             # 簡單的修改邏輯：讓使用者輸入新指令，然後重新規劃
             # 這裡簡化處理，直接返回 False 讓流程結束
             print("目前暫不支援動態修改計畫，請重新輸入更具體的指令。")
             return False
        else:
            return False

    def _decide_next_step(self) -> dict:
        """決定下一步執行哪個步驟"""
        # 找出第一個 pending 的步驟
        try:
            next_idx = self._plan_status.index("pending")
            step = self._current_plan[next_idx]
            
            return {
                "action": "dispatch",
                "step_index": next_idx,
                "agent_to_dispatch": step.get("agent", "chat"),
                "task_description": step.get("description", ""),
                "reasoning": "Executing next step in plan"
            }
        except ValueError:
            # 沒有 pending 的步驟了
            return {"action": "finish", "reasoning": "Plan completed"}

    def _dispatch_agent(self, agent_name: str, task_description: str) -> AgentResult:
        """調度 Agent"""
        agent = self.agents.get(agent_name)
        if not agent:
            # Fallback to chat if agent not found
            if "chat" in self.agents:
                agent = self.agents["chat"]
            else:
                return AgentResult(success=False, message=f"Agent {agent_name} not found")

        task = Task(
            query=task_description,
            task_type=self._current_context.task_type,
            symbols=self._current_context.symbols
        )
        
        # 執行
        # print(f"   ...呼叫 {agent.name}...") 
        return agent.execute(task)

    def _generate_final_report(self) -> str:
        """生成最終報告"""
        ctx = self._current_context
        if not ctx.agent_results:
            return "無法完成任務。"
            
        successful_results = [r for r in ctx.agent_results if r.success]
        if not successful_results:
            return "所有步驟執行失敗，請稍後再試。"

        if len(successful_results) == 1:
            return successful_results[0].message
        
        # 組合報告
        report = "### 執行報告\n\n"
        for r in successful_results:
            report += f"**{r.agent_name}**: {r.message}\n{'-'*20}\n"
        return report

    def _get_conversation_history(self) -> str:
        if not self._current_context: return ""
        return "\n".join(self._current_context.user_inputs)

    def _map_intent_to_task_type(self, intent: str) -> TaskType:
        mapping = {
            "news": TaskType.NEWS,
            "technical": TaskType.TECHNICAL,
            "tech": TaskType.TECHNICAL,
            "sentiment": TaskType.SENTIMENT,
            "chat": TaskType.GENERAL_CHAT,
            "general": TaskType.GENERAL_CHAT,
            "deep": TaskType.DEEP_ANALYSIS,
        }
        return mapping.get(intent.lower(), TaskType.GENERAL_CHAT)

    def _parse_json(self, content: str) -> dict:
        """解析 JSON 內容"""
        # 1. 嘗試直接解析
        try:
            return json.loads(content)
        except:
            pass
        
        # 2. 嘗試清理 Markdown 代碼塊
        try:
            cleaned = re.sub(r'```json\s*|\s*```', '', content)
            return json.loads(cleaned)
        except:
            pass

        # 3. 嘗試提取最外層 JSON (簡單版：找第一個 { 和最後一個 })
        try:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                json_str = content[start:end+1]
                return json.loads(json_str)
        except:
            pass

        return {}

    def get_status(self) -> dict:
        return {
            "session_id": self._session_id,
            "plan_length": len(self._current_plan),
            "plan_progress": f"{self._plan_status.count('completed')}/{len(self._plan_status)}",
            "agents": {n: a.get_status() for n, a in self.agents.items()}
        }

