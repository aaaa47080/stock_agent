import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.agents.manager import ManagerAgent, ManagerState
from core.agents.agent_registry import AgentRegistry
from core.agents.tool_registry import ToolRegistry
from core.agents.codebook import Codebook
from langchain_core.messages import AIMessage

# Mock LLM
class MockLLM:
    def invoke(self, messages):
        content = messages[0].content
        # print(f"MockLLM received: {content[:100]}...")
        if "AI 助手系統" in content:
            # Keep simple for basic async verification to avoid HITL interrupt handling complexity in script
            return AIMessage(content='{"complexity": "simple", "intent": "chat", "topics": ["TEST"]}')
        elif "classify" in content:
            return AIMessage(content='{"complexity": "simple", "intent": "chat", "topics": ["TEST"]}')
        elif "plan" in content:
             return AIMessage(content='{"plan": [{"step": 1, "description": "Say hello", "agent": "chat"}]}')
        elif "synthesize" in content:
            return AIMessage(content="Final Answer")
        return AIMessage(content="Mock response")

    async def ainvoke(self, messages):
        return self.invoke(messages)

# Mock Agent Registry
class MockAgentRegistry(AgentRegistry):
    def agents_info_for_prompt(self):
        return "Mock Agent Info"

# Mock Tool Registry
class MockToolRegistry(ToolRegistry):
    def list_all_tools(self):
        return []

# Mock Agent for Router
class MockAgent:
    def __init__(self, name):
        self.name = name
    
    def execute(self, task):
        import time
        # Simulate work (blocking, to prove run_in_executor works if events still fire?)
        # Actually in async test, we just want to ensure it runs.
        return type("AgentResult", (), {
            "success": True, 
            "message": f"Executed {task.description}", 
            "agent_name": self.name,
            "data": {}
        })

# Mock Router
class MockRouter:
    def route(self, name):
        return MockAgent(name)

async def main():
    print("Initializing ManagerAgent...")
    llm = MockLLM()
    agent_registry = MockAgentRegistry()
    tool_registry = MockToolRegistry()
    
    # Mock Codebook to avoid DB dependency
    class MockCodebook:
        def find_similar_entries(self, *args, **kwargs): return []
        def _persist_entry(self, *args, **kwargs): pass
        def _update_index(self, *args, **kwargs): pass
        def _cache(self): return {}
    codebook = MockCodebook()
    
    # Patch Router
    manager = ManagerAgent(llm, agent_registry, tool_registry, codebook)
    manager.router = MockRouter()
    
    # Test Async Invoke
    print("Testing manager.graph.ainvoke()...")
    
    events = []
    def on_progress(event):
        print(f"Callback Event: {event['type']}")
        events.append(event)
    
    manager.progress_callback = on_progress
    
    initial_state = {
        "session_id": "test-session",
        "query": "Hello Async World",
        "retry_count": 0,
    }
    config = {"configurable": {"thread_id": "test-thread"}}
    
    try:
        result = await manager.graph.ainvoke(initial_state, config)
        print(f"\nResult: {result.get('final_response')}")
        print(f"Total events captured: {len(events)}")
        
        # Verify success
        final_resp = result.get("final_response")
        if (final_resp == "Executed Hello Async World" or final_resp == "Final Answer") and len(events) > 0:
            print("\n✅ Verification SUCCESS: Async invoke worked and events streamed.")
        else:
            print("\n❌ Verification FAILED: output mismatch or no events.")
            
    except Exception as e:
        print(f"\n❌ Verification ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
