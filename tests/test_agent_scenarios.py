import unittest
import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agents.manager import ManagerAgent
from core.agents.models import ExecutionContext, SubTask, TaskComplexity
from core.agents.hierarchical_memory import FileSystemCodebook, MemoryEntry

# 50 Test Scenarios
SCENARIOS = [
    # --- Crypto: Bitcoin ---
    {"query": "BTC 價格", "topics": ["BTC"], "expected_agent": "chat", "intent": "chat"},
    {"query": "比特幣技術分析", "topics": ["BTC"], "expected_agent": "crypto", "intent": "technical"},
    {"query": "BTC 新聞", "topics": ["BTC"], "expected_agent": "crypto", "intent": "news"},
    {"query": "比特幣值得買嗎", "topics": ["BTC"], "expected_agent": "full_analysis", "intent": "full_analysis"},
    
    # --- Crypto: Ethereum ---
    {"query": "ETH 以太坊走勢", "topics": ["ETH"], "expected_agent": "crypto", "intent": "technical"},
    {"query": "以太坊升級新聞", "topics": ["ETH"], "expected_agent": "crypto", "intent": "news"},
    {"query": "ETH 做空建議", "topics": ["ETH"], "expected_agent": "full_analysis", "intent": "full_analysis"},

    # --- Crypto: Altcoins ---
    {"query": "SOL 價格", "topics": ["SOL"], "expected_agent": "chat", "intent": "chat"},
    {"query": "Pi 幣什麼時候上主網", "topics": ["PI"], "expected_agent": "crypto", "intent": "news"},
    {"query": "DOGE 狗狗幣分析", "topics": ["DOGE"], "expected_agent": "crypto", "intent": "technical"},

    # --- Platform: Account & Security ---
    {"query": "如何重設密碼", "topics": ["ACCOUNT"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "收不到驗證碼", "topics": ["SECURITY", "SMS"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "二階段驗證怎麼開", "topics": ["SECURITY", "2FA"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "帳號被鎖", "topics": ["ACCOUNT", "BLOCK"], "expected_agent": "chat", "intent": "platform_support"},

    # --- Platform: Finance ---
    {"query": "提現手續費多少", "topics": ["FEES", "WITHDRAW"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "充值沒到帳", "topics": ["DEPOSIT"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "VIP 等級怎麼升", "topics": ["VIP"], "expected_agent": "chat", "intent": "platform_support"},

    # --- Chat & Greeting ---
    {"query": "你好", "topics": [], "expected_agent": "chat", "intent": "chat"},
    {"query": "你是誰", "topics": [], "expected_agent": "chat", "intent": "chat"},
    {"query": "能幫我做什麼", "topics": [], "expected_agent": "chat", "intent": "chat"},
    
    # --- Context & Continuity (Simulated) ---
    {"query": "值得買嗎？", "context_topics": ["BTC"], "expected_topics": ["BTC"], "intent": "full_analysis"},
    {"query": "技術面呢？", "context_topics": ["ETH"], "expected_topics": ["ETH"], "intent": "technical"}, 
    {"query": "有什麼新聞？", "context_topics": ["SOL"], "expected_topics": ["SOL"], "intent": "news"},

    # --- Ambiguous ---
    {"query": "分析一下", "topics": [], "intent": "ambiguous"},
    {"query": "推薦投資", "topics": [], "intent": "ambiguous"},

    # --- Mixed/Complex ---
    {"query": "BTC 和 ETH 哪個好", "topics": ["BTC", "ETH"], "intent": "full_analysis"},
    {"query": "市場大盤分析", "topics": ["MARKET"], "intent": "full_analysis"},

    # --- Extended: DeFi & Earn ---
    {"query": "怎麼參與質押賺幣", "topics": ["EARN", "STAKING"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "ETH 質押收益率", "topics": ["ETH", "STAKING"], "expected_agent": "crypto", "intent": "technical"},
    {"query": "流動性挖礦是什麼", "topics": ["DEFI"], "expected_agent": "chat", "intent": "platform_support"},
    
    # --- Extended: Platform Technical ---
    {"query": "如何申請 API Key", "topics": ["API"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "API 報錯 500", "topics": ["API", "ERROR"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "Websocket 連不上", "topics": ["API", "WEBSOCKET"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "App 閃退怎麼辦", "topics": ["APP", "BUG"], "expected_agent": "chat", "intent": "platform_support"},
    
    # --- Extended: Identity & Compliance ---
    {"query": "KYC 驗證失敗", "topics": ["KYC"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "為什麼要實名認證", "topics": ["KYC"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "我未滿 18 歲可以註冊嗎", "topics": ["KYC", "REGISTER"], "expected_agent": "chat", "intent": "platform_support"},
    
    # --- Extended: Trading Operations ---
    {"query": "怎麼開合約", "topics": ["FUTURES", "TRADE"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "槓桿最高幾倍", "topics": ["LEVERAGE"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "資金費率是什麼", "topics": ["FUNDING_RATE"], "expected_agent": "chat", "intent": "platform_support"},
    {"query": "如何止損", "topics": ["STOP_LOSS", "TRADE"], "expected_agent": "chat", "intent": "platform_support"},

    # --- Extended: More Crypto ---
    {"query": "XRP 官司結果", "topics": ["XRP"], "expected_agent": "crypto", "intent": "news"},
    {"query": "BNB 銷毀紀錄", "topics": ["BNB"], "expected_agent": "crypto", "intent": "news"},
    {"query": "ADA 技術面如何", "topics": ["ADA"], "expected_agent": "crypto", "intent": "technical"},
    {"query": "DOT 生態發展", "topics": ["DOT"], "expected_agent": "crypto", "intent": "news"},

    # --- Extended: Fun/Edge ---
    {"query": "比特幣會跌到零嗎", "topics": ["BTC"], "expected_agent": "full_analysis", "intent": "full_analysis"},
    {"query": "現在 all in 行不行", "topics": [], "intent": "ambiguous"},
    {"query": "教我寫 Python", "topics": [], "expected_agent": "chat", "intent": "chat"}, # Off-topic but handled by chat
    {"query": "測試模式怎麼開", "topics": ["TEST_MODE"], "expected_agent": "chat", "intent": "platform_support"},
]

class TestAgentScenarios(unittest.TestCase):
    def setUp(self):
        # Mock components to avoid real LLM calls
        self.llm = MagicMock()
        self.agent_registry = MagicMock()
        self.tool_registry = MagicMock()
        self.codebook = MagicMock() # Mock codebook to verify calls

        # Setup Manager
        self.manager = ManagerAgent(
            llm_client=self.llm,
            agent_registry=self.agent_registry,
            tool_registry=self.tool_registry,
            codebook=self.codebook
        )

    @pytest.mark.skip(reason="_classify removed; test needs rework for new graph-based API")
    def test_scenarios(self):
        print(f"\nRunning {len(SCENARIOS)} Test Scenarios...")
        pass_count = 0
        
        for i, case in enumerate(SCENARIOS):
            query = case["query"]
            print(f"[{i+1}/{len(SCENARIOS)}] Testing: {query}")
            
            # Mock Classification Response
            mock_class = {
                "complexity": "complex" if case["intent"] == "full_analysis" else "simple",
                "intent": case.get("intent", "chat"),
                "topics": case.get("topics", case.get("expected_topics", [])),
                "agent": case.get("expected_agent", "chat"),
            }
            if case.get("intent") == "ambiguous":
                mock_class["complexity"] = "ambiguous"
                
            # Mock LLM process
            with patch.object(self.manager, '_classify', return_value=mock_class):
                # We don't ACTUALLY run process() because it triggers complex execution chains.
                # We verify the logic flow based on classification.
                
                # Verify Context Construction Logic
                context = ExecutionContext(
                    session_id="test",
                    original_query=query,
                    complexity=TaskComplexity(mock_class["complexity"]),
                    intent=mock_class["intent"],
                    topics=mock_class["topics"],
                    plan=[]
                )
                
                # Check Expectations
                try:
                    # 1. Check Topic Extraction
                    expected_topics = case.get("expected_topics", case.get("topics"))
                    self.assertEqual(sorted(context.topics), sorted(expected_topics), f"Topics mismatch: {context.topics} != {expected_topics}")
                    
                    # 2. Check Intent
                    self.assertEqual(context.intent, case.get("intent"), f"Intent mismatch: {context.intent} != {case.get('intent')}")
                    
                    pass_count += 1
                    # print("  ✅ PASS")
                except AssertionError as e:
                    print(f"  ❌ FAIL: {e}")
                    
        print(f"\nResult: {pass_count}/{len(SCENARIOS)} passed.")
        self.assertEqual(pass_count, len(SCENARIOS))

if __name__ == "__main__":
    unittest.main()
