"""
Agent V4 — News Agent

新聞搜集 Agent: 多來源新聞聚合與總結。
"""
from typing import Optional

from langchain_core.messages import HumanMessage

# from ..base import SubAgent
from ..models import SubTask, AgentResult
from ..prompt_registry import PromptRegistry


class NewsAgent:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "news"

    def execute(self, task: SubTask) -> AgentResult:
        """Execute news gathering and summarization."""
        symbol = self._extract_symbol(task.description)

        # Step 1: Gather news
        all_news = []
        
        # Tools to try
        tools_to_try = [
            ("google_news", {"symbol": symbol, "limit": 5}),
            ("aggregate_news", {"symbol": symbol, "limit": 5}),
            # If explicit "Pi" symbol, prefer web search if others likely fail?
            # Or just fallback.
        ]
        
        for t_name, t_args in tools_to_try:
            tool = self.tool_registry.get(t_name, caller_agent=self.name)
            if tool:
                try:
                    res = tool.handler.invoke(t_args)
                    if isinstance(res, list):
                        for news in res:
                            news["symbol"] = symbol
                            all_news.append(news)
                except Exception:
                    pass
        
        # V5 improvement: Fallback to web_search if essentially empty
        if len(all_news) == 0:
            ws_tool = self.tool_registry.get("web_search", caller_agent=self.name)
            if ws_tool:
                try:
                    # Search query
                    q = f"{symbol} crypto news latest"
                    res_str = ws_tool.handler.invoke({"query": q, "purpose": "news_agent_fallback"})
                    # We might get a string back suitable for LLM but not list of dicts.
                    # We'll treat it as one "summary" item or parse it?
                    # For simplicity, append raw text as a "source"
                    all_news.append({"title": "Web Search Result", "source": "DuckDuckGo", "description": res_str})
                except Exception:
                    pass

        # Step 2: Check result
        if not all_news:
             return AgentResult(
                success=False,
                message=f"抱歉，無法獲取 {symbol} 的相關新聞 (Refused: No Data)。",
                agent_name=self.name,
                quality="fail"
            )

        # Step 3: Format
        news_text = ""
        for n in all_news[:10]:
            title = n.get('title', 'No Title')
            desc = n.get('description', '')[:200]
            news_text += f"- {title}\n  摘要: {desc}...\n"

        # Step 4: Summarize
        prompt = PromptRegistry.render(
            "news_agent", "summarize",
            symbol=symbol,
            news_items=news_text,
            query=task.description,
        )

        try:
            # Check for refusal in prompt output?
            # V5 Prompt has refusal instructions.
            response = self.llm.invoke([HumanMessage(content=prompt)])
            summary = response.content
            
            # Check for JSON Refusal
            if "REFUSED" in summary:
                 return AgentResult(
                    success=False,
                    message=f"Agent Refused Task: {summary}",
                    agent_name=self.name,
                    quality="fail"
                )
                
        except Exception as e:
            summary = f"（新聞總結生成失敗：{e}）"

        # Step 5: Format output
        output = self._format_output(all_news[:10], summary)

        # We skipped custom quality assessment here for brevity/native pattern.
        # Ideally Watcher Agent (Supervisor) handles the QA now.
        
        return AgentResult(
            success=True,
            message=output,
            agent_name=self.name,
            data={"news": all_news, "summary": summary},
            quality="pass",
        )

    def _format_output(self, news_list: list, summary: str) -> str:
        lines = [f"### 📰 **{news_list[0].get('symbol', 'Crypto')} 市場動態摘要**", "", f"> {summary}", "", "---", "#### 📋 **精選新聞**", ""]
        for i, news in enumerate(news_list, 1):
            title = news.get('title', 'No Title')
            source = news.get('source', 'Unknown')
            url = news.get('url') or news.get('link')
            
            # Title with Link if available
            title_line = f"**{i}. [{title}]({url})**" if url else f"**{i}. {title}**"
            lines.append(f"{title_line} _({source})_")
            
            desc = news.get('description', '')
            if desc and "Web Search Result" not in title:
                 # Clean up desc if too long
                 clean_desc = desc[:150] + "..." if len(desc) > 150 else desc
                 lines.append(f"> {clean_desc}")
            lines.append("")
        return "\n".join(lines)

    def _extract_symbol(self, description: str) -> str:
        from langchain_core.messages import HumanMessage
        try:
            prompt_text = PromptRegistry.render(
                "news_agent", "extract_symbol",
                description=description
            )
            response = self.llm.invoke([HumanMessage(content=prompt_text)])
            return response.content.strip().upper().split()[0]
        except Exception:
            return "BTC"
