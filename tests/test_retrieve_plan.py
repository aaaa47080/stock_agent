import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agents.manager import ManagerAgent
from core.agents.models import ExecutionContext, TaskComplexity
from core.agents.hierarchical_memory import MemoryEntry

class TestRetrieveThenPlan(unittest.TestCase):
    def setUp(self):
        self.llm = MagicMock()
        self.agent_registry = MagicMock()
        self.tool_registry = MagicMock()
        self.hitl = MagicMock()
        self.codebook = MagicMock()
        
        self.manager = ManagerAgent(
            llm_client=self.llm,
            agent_registry=self.agent_registry,
            tool_registry=self.tool_registry,
            hitl=self.hitl,
            codebook=self.codebook
        )

    def test_plan_receives_past_experience(self):
        # Setup Context
        context = ExecutionContext(
            session_id="test",
            original_query="Complex Query",
            complexity=TaskComplexity.COMPLEX,
            intent="full_analysis",
            topics=["BTC"],
            plan=[]
        )
        
        # Mock Codebook Return
        mock_entry = MemoryEntry(
            id="123", query="Similar Query", intent="full_analysis", topics=["BTC"],
            plan=[{"step": 1, "description": "Step 1", "agent": "news", "tool_hint": None}],
            complexity="complex", created_at="2023-01-01", ttl_days=14
        )
        self.codebook.find_similar_entries.return_value = [mock_entry]
        self.manager._hitl_confirm_plan = MagicMock(return_value=False) # Stop execution after plan

        # Execute
        self.manager._execute_complex(context, "test")
        
        # Verify Codebook was called
        self.codebook.find_similar_entries.assert_called_once()
        
        # Verify LLM Prompt contained the past experience
        # We need to inspect the call args to llm.invoke
        call_args = self.llm.invoke.call_args
        prompt_text = call_args[0][0][0].content
        print(f"Prompt Content:\n{prompt_text}")
        
        self.assertIn("Similar Query", prompt_text)
        self.assertIn("Step 1", prompt_text)
        print("✅ Past experience successfully injected into Prompt")

if __name__ == "__main__":
    unittest.main()
