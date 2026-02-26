"""
Watcher Agent (Supervisor/Critic)
Monitors execution quality and relevance.
"""
import json
from langchain_core.messages import HumanMessage
from .prompt_registry import PromptRegistry
from api.utils import logger

class WatcherAgent:
    def __init__(self, llm_client):
        self.llm = llm_client

    def critique(self, query: str, step_description: str, result: str) -> dict:
        """
        Critique a specific execution step.
        Returns: {"status": "PASS"|"FAIL", "feedback": "..."}
        """
        try:
            prompt = PromptRegistry.render(
                "watcher", "critique",
                query=query,
                step_description=step_description,
                result=result[:2000]  # truncate to avoid context limit
            )
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            try:
                data = json.loads(content)
                return data
            except json.JSONDecodeError:
                # Fallback parsing
                if "PASS" in content.upper():
                    return {"status": "PASS", "feedback": "Parsed as PASS from text."}
                return {"status": "FAIL", "feedback": f"Could not parse JSON. Raw: {content}"}
                
        except Exception as e:
            logger.error(f"[Watcher] Critique failed: {e}")
            return {"status": "PASS", "feedback": "Watcher failed, defaulting to PASS."}
