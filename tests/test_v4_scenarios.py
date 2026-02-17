import sys
import os
import time
import uuid
import logging
import random
from unittest.mock import patch

# Add project root to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from core.agents.bootstrap import bootstrap
from core.agents.manager import V4State
from utils.llm_client import LLMClientFactory

# Setup logging
logging.basicConfig(level=logging.ERROR)  # suppress debug noise
logger = logging.getLogger("TEST")
logger.setLevel(logging.INFO)

def run_test_session(session_id: str, queries: list, manager=None):
    """Run a sequence of queries in a session."""
    if not manager:
        provider = os.getenv("LLM_PROVIDER", "openai")
        client = LLMClientFactory.create_client(provider)
        manager = bootstrap(client)
    
    print(f"\n--- Session {session_id} ---")
    for q in queries:
        print(f"\nUser: {q}")
        start = time.time()
        
        # Manually invoke manager process
        # Manager process signature: process(query, session_id)
        # But manager.process() returns generator or print?
        # Let's check manager.py process()
        # It yields chunks.
        
        try:
            # manager.process returns the final response string directly
            # Patch input to avoid blocking on HITL
            with patch('builtins.input', return_value=""):
                response_text = manager.process(q, session_id)
            if "ERROR" in response_text:
                return False, response_text
            return True, response_text
        except Exception as e:
            print(f"Error processing {q}: {e}")
            response_text = f"ERROR: {e}"
            
        print(f"Agent: {str(response_text).strip()}")
        print(f"(Time: {time.time() - start:.2f}s)")
        
    return manager


def run_varied_stress_test(count: int = 50):
    """Run a stress test with VARIOUS scenarios (Identity, Analysis, News)."""
    print(f"\n🚀 Starting Varied Stress Test: {count} iterations")
    
    names = ["Alice", "Bob", "Charlie", "Danny", "Eve"]
    coins = ["BTC", "ETH", "SOL", "DOGE", "BNB"]
    
    provider = os.getenv("LLM_PROVIDER", "openai")
    client = LLMClientFactory.create_client(provider)

    stats = {
        "identity": {"total": 0, "pass": 0},
        "analysis": {"total": 0, "pass": 0},
        "news": {"total": 0, "pass": 0}
    }

    for i in range(count):
        session_id = str(uuid.uuid4())
        scenario_type = random.choice(["identity", "analysis", "news"])
        # weight analysis lower as it consumes more tokens/time?
        # Let's keep equal or random.
        
        print(f"\n--- Iteration {i+1}/{count} [{scenario_type.upper()}] (Session {session_id[:8]}) ---")
        
        try:
            # Refresh manager periodically
            if i == 0 or i % 10 == 0:
                manager = bootstrap(client)
            
            if scenario_type == "identity":
                stats["identity"]["total"] += 1
                name = random.choice(names)
                # 1. Identity
                q1 = f"我是 {name}"
                with patch('builtins.input', return_value=""):
                    r1 = manager.process(q1, session_id)
                
                # 2. History Recall
                q2 = "我叫什麼名字？"
                with patch('builtins.input', return_value=""):
                    r2 = manager.process(q2, session_id)
                
                if name in r2:
                    print(f"✅ Identity Passed: {name}")
                    stats["identity"]["pass"] += 1
                else:
                    print(f"❌ Identity Failed: Expected {name}, Got {r2[:50]}...")

            elif scenario_type == "analysis":
                stats["analysis"]["total"] += 1
                coin = random.choice(coins)
                # Complex query: "Analyze BTC comprehensive"
                q = f"請詳細分析 {coin} (價格+新聞)"
                with patch('builtins.input', return_value=""):
                    r = manager.process(q, session_id)
                
                # Check for keywords indicating extensive analysis
                # Expecting: "Price", "News", "Analysis"
                valid = False
                if any(k in r for k in ["價格", "Price", "$"]) and \
                   any(k in r for k in ["新聞", "News", "報導"]) and \
                   len(r) > 100:
                    valid = True
                
                if valid:
                    print(f"✅ Analysis Passed: {coin} (Length: {len(r)})")
                    stats["analysis"]["pass"] += 1
                else:
                    print(f"❌ Analysis Failed: {coin} Response: {r[:100]}...")

            elif scenario_type == "news":
                stats["news"]["total"] += 1
                coin = random.choice(coins)
                q = f"{coin} 最新新聞"
                with patch('builtins.input', return_value=""):
                    r = manager.process(q, session_id)
                
                if "新聞" in r or "報導" in r:
                    print(f"✅ News Passed: {coin}")
                    stats["news"]["pass"] += 1
                else:
                     print(f"❌ News Failed: {r[:50]}...")
                
        except Exception as e:
            print(f"🔥 Exception: {e}")
            
    print("\n📊 Stress Test Results:")
    total_pass = 0
    for k, v in stats.items():
        if v["total"] > 0:
            rate = v["pass"] / v["total"] * 100
            print(f"  - {k.capitalize()}: {v['pass']}/{v['total']} ({rate:.1f}%)")
            total_pass += v["pass"]
    
    print(f"  - TOTAL: {total_pass}/{count} ({total_pass/count*100:.1f}%)")


# Define Test Scenarios

scenarios = [
    {
        "name": "Basic Chat & Identity",
        "queries": [
            "你好",
            "我是測試員 T-800",
            "我叫什麼名字？"
        ]
    },
    {
        "name": "Crypto Tools",
        "queries": [
            "BTC 價格",
            "ETH 技術分析",
            "PI Network 有什麼新聞"
        ]
    },
    {
        "name": "Edge Cases & Rejection",
        "queries": [
            "台北天氣如何",
            "幫我訂機票",
            "寫一段 Python 程式碼"
        ]
    },
    {
        "name": "Meta Questions (History)",
        "queries": [
            "我剛才問了 PI 的新聞嗎？",
            "我們這段對話聊了什麼？"
        ]
    }
]

def main():
    session_id = str(uuid.uuid4())
    print(f"Starting Benchmark User ID: {session_id}")
    
    # Run all scenarios in ONE session to test context retention?
    # Or separate? User wants "Thorough test".
    # Let's run linear flow.
    
    provider = os.getenv("LLM_PROVIDER", "openai")
    client = LLMClientFactory.create_client(provider)
    manager = bootstrap(client)
    
    # 1. Identity & Memory
    print("\n🟢 TEST 1: Identity & Memory")
    run_test_session(session_id, [
        "你好",
        "我是測試員 T-800", 
        "我叫什麼名字？"  # Should reply T-800
    ], manager)
    
    # 2. Tools
    # print("\n🟢 TEST 2: Tools Usage")
    # run_test_session(session_id, [
    #     "BTC 現在多少錢？",
    #     "分析一下 ETH 的 RSI",
    #     "最近 SOL 有什麼大新聞？"
    # ], manager)
    
    # 3. Persistence Check (Simulate Restart by creating NEW manager instance)
    print("\n🟢 TEST 3: Persistence (Restart Manager)")
    print("... Re-bootstrapping Manager ...")
    del manager
    provider = os.getenv("LLM_PROVIDER", "openai")
    client = LLMClientFactory.create_client(provider)
    manager2 = bootstrap(client)
    
    run_test_session(session_id, [
         "我叫什麼名字？", # Should still know T-800
         "我剛才問了哪幾個幣？" # Should know BTC, ETH, SOL
    ], manager2)
    
    # 4. Out of Scope
    # print("\n🟢 TEST 4: Rejection")
    # run_test_session(session_id, [
    #     "明天會下雨嗎？", # Should reject
    #     "幫我買 100 顆 BTC" # Should reject (trading not supported yet or purely info)
    # ], manager2)

def run_realistic_simulation(count: int = 20):
    """Run simulation with Trader vs Newbie personas."""
    print(f"\n🚀 Starting Realistic User Simulation: {count} sessions")
    
    provider = os.getenv("LLM_PROVIDER", "openai")
    client = LLMClientFactory.create_client(provider)
    
    personas = {
        "trader": [
            "BTC price", 
            "Analyze chart for it",  # Context: "it" -> BTC
            "News about SOL",        # Switch topic
            "Compare with ETH"       # Complex/Ambiguous
        ],
        "newbie": [
            "Hi there",
            "What is Bitcoin exactly?",
            "Is it safe to invest?",
            "How do I start?"
        ]
    }

    for i in range(count):
        session_id = str(uuid.uuid4())
        persona_name = random.choice(list(personas.keys()))
        queries = personas[persona_name]
        
        print(f"\n--- Session {i+1}/{count} [{persona_name.upper()}] (ID: {session_id[:8]}) ---")
        
        # Fresh manager for each session to simulate new user
        if i == 0 or i % 5 == 0:
            manager = bootstrap(client)
            
        history = []
        for q in queries:
            print(f"User: {q}")
            with patch('builtins.input', return_value=""):
                resp = manager.process(q, session_id)
            print(f"Agent: {resp[:100]}..." if len(resp) > 100 else f"Agent: {resp}")
            history.append((q, resp))
            
            # Simple validation
            if persona_name == "trader" and "price" in q and "$" not in resp and "價格" not in resp:
                 print("⚠️ Warning: Price query might have failed")
            if persona_name == "newbie" and "Bitcoin" in q and "比特幣" not in resp and "Bitcoin" not in resp:
                 print("⚠️ Warning: Explanation might be off")

    print("\n✅ Simulation Complete.")

if __name__ == "__main__":
    # main()
    # run_varied_stress_test(50)
    run_realistic_simulation(20)
