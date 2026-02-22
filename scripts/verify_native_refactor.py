"""
Verification script for Native LangGraph Refactor.
Tries to bootstrap the agent system and print keys to ensure no crash.
"""
import sys
import os

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from core.agents.bootstrap import bootstrap
    from utils.llm_client import LLMClientFactory
    
    print("Initializing LLM Client...")
    # Use factory to create a standard OpenAI client (or from env)
    llm = LLMClientFactory.create_client("openai")
    
    print("Bootstrapping ManagerAgent...")
    manager = bootstrap(llm, web_mode=False)
    
    print("Manager Status:")
    print(manager.get_status())
    
    print("SUCCESS: System bootstrapped without error.")
except ImportError as e:
    print(f"FAIL: ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAIL: Exception: {e}")
    sys.exit(1)
