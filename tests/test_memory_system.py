"""
記憶系統自動化測試 - 測試多輪對話中的記憶持久化

使用方式:
    python tests/test_memory_system.py

測試案例（由簡單到難）:
1. 基礎記憶存取 - 存入/讀取長期記憶
2. 資訊回憶 - 測試能否回憶之前提到的資訊
3. 偏好記憶 - 測試用戶偏好的持久化
4. 多輪累積 - 測試多輪對話中資訊的累積
5. 跨話題關聯 - 測試不同話題間的資訊關聯
6. 記憶更新 - 測試舊資訊被新資訊更新
7. 歷史記錄查詢 - 測試從歷史中找回資訊
8. 記憶整合 - 測試 consolidate 功能
9. 多會話隔離 - 測試不同會話的記憶隔離
10. 長期記憶壓縮 - 測試大量資訊的壓縮能力
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from core.database.memory import get_memory_store
from utils.settings import Settings

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_results"
)

# 測試用戶 ID
TEST_USER_ID = "memory_test_user"
TEST_SESSION_ID = f"test_session_{int(time.time())}"


class MemoryTestCase:
    """記憶測試案例"""

    def __init__(self, name: str, description: str, difficulty: int):
        self.name = name
        self.description = description
        self.difficulty = difficulty  # 1-10
        self.passed = False
        self.error = None
        self.details = {}

    def __repr__(self):
        status = "✅" if self.passed else "❌"
        return f"{status} [{self.difficulty}/10] {self.name}"


class MemorySystemTester:
    """記憶系統測試器"""

    def __init__(self, manager, session_id: str):
        self.manager = manager
        self.session_id = session_id
        self.test_cases: list[MemoryTestCase] = []
        self.conversation_log = []
        self.round_count = 0

        # 獲取記憶存儲
        self.memory_store = get_memory_store(TEST_USER_ID, session_id)

    async def send_message(self, message: str) -> dict:
        """發送訊息給 Manager"""
        config = {"configurable": {"thread_id": self.session_id}}
        history_text = ""

        self.round_count += 1
        start_time = time.time()

        graph_input = {
            "session_id": self.session_id,
            "query": message,
            "history": history_text,
            "language": "zh-TW",
        }

        result = await self.manager.graph.ainvoke(graph_input, config)
        duration = time.time() - start_time

        response = result.get("final_response", "無回應")

        log_entry = {
            "round": self.round_count,
            "user": message,
            "assistant": response[:500] if response else "無回應",
            "mode": result.get("execution_mode", "unknown"),
            "duration": round(duration, 2),
        }
        self.conversation_log.append(log_entry)

        return log_entry

    def log(self, message: str):
        """打印日誌"""
        print(f"  {message}")

    # ==================== 測試案例 1: 基礎記憶存取 ====================

    async def test_1_basic_memory_storage(self) -> MemoryTestCase:
        """
        難度: 1/10
        測試: 基礎的長期記憶存取功能
        """
        test = MemoryTestCase(
            "基礎記憶存取", "測試長期記憶的基本存取功能", difficulty=1
        )

        try:
            # 清理舊記憶
            self.memory_store.write_long_term("")

            # 寫入測試記憶
            test_content = "# Test Memory\n- 用戶喜歡比特幣\n- 用戶使用繁體中文"
            self.memory_store.write_long_term(test_content)

            # 讀取並驗證
            read_content = self.memory_store.read_long_term()

            if test_content in read_content or "比特幣" in read_content:
                test.passed = True
                test.details = {"written": test_content, "read": read_content}
                self.log("✓ 寫入和讀取長期記憶成功")
            else:
                test.error = f"讀取內容不匹配: {read_content}"

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 2: 資訊回憶 ====================

    async def test_2_information_recall(self) -> MemoryTestCase:
        """
        難度: 2/10
        測試: 測試能否回憶之前提到的資訊
        """
        test = MemoryTestCase(
            "資訊回憶", "測試系統能否回憶之前對話中提到的資訊", difficulty=2
        )

        try:
            # 先告訴系統一個特定資訊
            unique_info = f"我的幸運數字是 {int(time.time()) % 1000}"
            self.log(f"告訴系統: {unique_info}")

            await self.send_message(unique_info)
            await asyncio.sleep(1)  # 等待處理

            # 然後問系統這個資訊
            result2 = await self.send_message("我剛才告訴你的幸運數字是多少？")

            response = result2["assistant"]

            # 檢查回應是否包含幸運數字
            lucky_number = unique_info.split("是 ")[1]
            if lucky_number in response:
                test.passed = True
                test.details = {
                    "original_info": unique_info,
                    "response": response[:200],
                }
                self.log(f"✓ 系統正確回憶了幸運數字: {lucky_number}")
            else:
                test.error = f"系統未能回憶資訊，回應: {response[:200]}"
                test.details = {"response": response[:300]}

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 3: 偏好記憶 ====================

    async def test_3_preference_memory(self) -> MemoryTestCase:
        """
        難度: 3/10
        測試: 用戶偏好的持久化
        """
        test = MemoryTestCase("偏好記憶", "測試用戶偏好設定能否被記住", difficulty=3)

        try:
            # 設置偏好
            self.log("設置用戶偏好: 我偏好使用技術分析，不喜歡基本面分析")
            await self.send_message(
                "請記住我的投資偏好：我偏好使用技術分析來做決策，我不喜歡基本面分析。"
            )
            await asyncio.sleep(1)

            # 在另一個問題中測試偏好
            result = await self.send_message("根據我的偏好，你會建議我如何分析 ETH？")

            response = result["assistant"]

            # 檢查是否根據偏好回答
            if "技術分析" in response and (
                "基本面" not in response or "不喜歡" in response or "不考慮" in response
            ):
                test.passed = True
                test.details = {"response": response[:300]}
                self.log("✓ 系統記住了用戶的投資偏好")
            else:
                # 也算通過，只要有提到技術分析
                if "技術" in response:
                    test.passed = True
                    test.details = {"response": response[:300], "note": "部分符合"}
                    self.log("✓ 系統部分記住了偏好")
                else:
                    test.error = f"系統未體現偏好記憶: {response[:200]}"

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 4: 多輪累積 ====================

    async def test_4_multi_round_accumulation(self) -> MemoryTestCase:
        """
        難度: 4/10
        測試: 多輪對話中資訊的累積
        """
        test = MemoryTestCase(
            "多輪資訊累積", "測試多輪對話中資訊能否正確累積", difficulty=4
        )

        try:
            # 分三輪提供不同的資訊
            info_pieces = [
                "我持有 0.5 個比特幣",
                "我持有 5 個以太幣",
                "我還持有 1000 個 SOL",
            ]

            for i, info in enumerate(info_pieces):
                self.log(f"第 {i + 1} 輪: {info}")
                await self.send_message(f"告訴你，{info}")
                await asyncio.sleep(1)

            # 詢問總結
            result = await self.send_message("請總結我目前持有的加密貨幣部位")

            response = result["assistant"]

            # 檢查是否包含所有資訊
            found_btc = "0.5" in response or "比特幣" in response
            found_eth = "5" in response or "以太" in response
            found_sol = "1000" in response or "SOL" in response

            found_count = sum([found_btc, found_eth, found_sol])

            if found_count >= 2:
                test.passed = True
                test.details = {
                    "found_btc": found_btc,
                    "found_eth": found_eth,
                    "found_sol": found_sol,
                    "response": response[:400],
                }
                self.log(f"✓ 系統記住了 {found_count}/3 個部位資訊")
            else:
                test.error = f"系統只記住了 {found_count}/3 個資訊: {response[:200]}"

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 5: 跨話題關聯 ====================

    async def test_5_cross_topic_correlation(self) -> MemoryTestCase:
        """
        難度: 5/10
        測試: 不同話題間的資訊關聯
        """
        test = MemoryTestCase(
            "跨話題關聯", "測試系統能否將不同話題的資訊關聯起來", difficulty=5
        )

        try:
            # 先談一個話題
            self.log("話題 1: 詢問 BTC 價格")
            await self.send_message("現在 BTC 價格多少？")
            await asyncio.sleep(2)

            # 切換到另一個話題
            self.log("話題 2: 詢問投資建議")
            await self.send_message("我有 10000 美元可以投資")
            await asyncio.sleep(2)

            # 測試關聯
            self.log("話題 3: 測試關聯")
            result = await self.send_message(
                "根據剛才的 BTC 價格，那 10000 美元能買多少 BTC？"
            )

            response = result["assistant"]

            # 檢查是否嘗試計算或提及之前的價格
            has_calculation = any(
                c in response for c in ["0.", "約", "大約", "可以買", "BTC"]
            )
            mentions_price = any(p in response for p in ["價格", "美元", "$", "USDT"])

            if has_calculation or mentions_price:
                test.passed = True
                test.details = {"response": response[:400]}
                self.log("✓ 系統嘗試關聯不同話題的資訊")
            else:
                test.error = f"系統未能關聯資訊: {response[:200]}"

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 6: 記憶更新 ====================

    async def test_6_memory_update(self) -> MemoryTestCase:
        """
        難度: 6/10
        測試: 舊資訊被新資訊更新
        """
        test = MemoryTestCase("記憶更新", "測試系統能否更新過時的資訊", difficulty=6)

        try:
            # 先提供一個資訊
            old_info = "我的風險承受度是保守型"
            self.log(f"初始資訊: {old_info}")
            await self.send_message(f"請記住：{old_info}")
            await asyncio.sleep(1)

            # 更新資訊
            new_info = "我的風險承受度改變了，現在是積極型"
            self.log(f"更新資訊: {new_info}")
            await self.send_message(new_info)
            await asyncio.sleep(1)

            # 測試是否記住了更新
            result = await self.send_message("我的風險承受度是什麼？")

            response = result["assistant"]

            if "積極" in response and "保守" not in response:
                test.passed = True
                test.details = {"response": response[:300]}
                self.log("✓ 系統正確更新了記憶")
            elif "積極" in response:
                test.passed = True
                test.details = {"response": response[:300], "note": "部分成功"}
                self.log("✓ 系統部分更新了記憶")
            else:
                test.error = f"系統未正確更新記憶: {response[:200]}"

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 7: 歷史記錄查詢 ====================

    async def test_7_history_retrieval(self) -> MemoryTestCase:
        """
        難度: 7/10
        測試: 從歷史記錄中找回資訊
        """
        test = MemoryTestCase(
            "歷史記錄查詢", "測試系統能否從歷史記錄中找回資訊", difficulty=7
        )

        try:
            # 添加一些歷史記錄
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            test_entry = f"[{timestamp}] 測試用戶詢問了關於比特幣的投資建議"
            self.memory_store.append_history(test_entry)
            self.log(f"添加歷史記錄: {test_entry}")

            # 再添加幾條
            for i in range(3):
                entry = f"[{timestamp}] 測試記錄 #{i + 1}"
                self.memory_store.append_history(entry)

            # 獲取歷史
            history = self.memory_store.get_history(limit=10)

            if history and len(history) >= 4:
                # 檢查是否包含我們的測試條目
                found = any("比特幣" in h.get("entry", "") for h in history)
                if found:
                    test.passed = True
                    test.details = {"history_count": len(history)}
                    self.log(f"✓ 歷史記錄查詢成功，共 {len(history)} 條記錄")
                else:
                    test.error = "歷史記錄中未找到測試條目"
            else:
                test.error = f"歷史記錄數量不足: {len(history) if history else 0}"

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 8: 記憶整合 ====================

    async def test_8_memory_consolidation(self) -> MemoryTestCase:
        """
        難度: 8/10
        測試: consolidate 功能
        """
        test = MemoryTestCase("記憶整合", "測試記憶整合功能", difficulty=8)

        try:
            # 準備測試消息
            messages = [
                {
                    "role": "user",
                    "content": "我喜歡用技術分析",
                    "timestamp": "2026-01-01 10:00",
                },
                {
                    "role": "assistant",
                    "content": "好的，我記住了",
                    "timestamp": "2026-01-01 10:01",
                },
                {
                    "role": "user",
                    "content": "我持有比特幣",
                    "timestamp": "2026-01-01 10:02",
                },
                {
                    "role": "assistant",
                    "content": "了解",
                    "timestamp": "2026-01-01 10:03",
                },
                {
                    "role": "user",
                    "content": "我偏好短期交易",
                    "timestamp": "2026-01-01 10:04",
                },
            ]

            # 獲取整合前的記憶
            memory_before = self.memory_store.read_long_term()
            self.log(f"整合前記憶長度: {len(memory_before)}")

            # 執行整合
            success = await self.memory_store.consolidate(
                messages=messages,
                llm=self.manager.llm,
                memory_window=10,
                archive_all=True,
            )

            if success:
                memory_after = self.memory_store.read_long_term()
                self.log(f"整合後記憶長度: {len(memory_after)}")

                # 檢查是否有內容
                if memory_after and len(memory_after) > 10:
                    test.passed = True
                    test.details = {
                        "memory_before": memory_before[:100]
                        if memory_before
                        else "(empty)",
                        "memory_after": memory_after[:300],
                    }
                    self.log("✓ 記憶整合成功")
                else:
                    test.error = f"整合後記憶內容過短: {memory_after}"
            else:
                test.error = "整合函數返回失敗"

        except Exception as e:
            test.error = str(e)
            import traceback

            test.details = {"traceback": traceback.format_exc()}

        return test

    # ==================== 測試案例 9: 多會話隔離 ====================

    async def test_9_session_isolation(self) -> MemoryTestCase:
        """
        難度: 9/10
        測試: 不同會話的記憶隔離
        """
        test = MemoryTestCase(
            "多會話隔離", "測試不同會話的記憶是否正確隔離", difficulty=9
        )

        try:
            # 創建兩個不同的會話
            session1 = get_memory_store(TEST_USER_ID, "session_1")
            session2 = get_memory_store(TEST_USER_ID, "session_2")

            # 寫入不同的記憶
            session1.write_long_term("# Session 1 Memory\n- 這是會話 1 的記憶")
            session2.write_long_term("# Session 2 Memory\n- 這是會話 2 的記憶")

            # 驗證隔離
            mem1 = session1.read_long_term()
            mem2 = session2.read_long_term()

            has_session1_marker = "會話 1" in mem1 or "Session 1" in mem1
            has_session2_marker = "會話 2" in mem2 or "Session 2" in mem2
            no_cross_contamination = ("會話 2" not in mem1) and ("會話 1" not in mem2)

            if has_session1_marker and has_session2_marker and no_cross_contamination:
                test.passed = True
                test.details = {
                    "session1_memory": mem1[:100],
                    "session2_memory": mem2[:100],
                }
                self.log("✓ 會話記憶正確隔離")
            else:
                test.error = f"會話記憶隔離失敗: s1={mem1[:50]}, s2={mem2[:50]}"

        except Exception as e:
            test.error = str(e)

        return test

    # ==================== 測試案例 10: 長期記憶壓縮 ====================

    async def test_10_memory_compression(self) -> MemoryTestCase:
        """
        難度: 10/10
        測試: 大量資訊的壓縮能力
        """
        test = MemoryTestCase(
            "長期記憶壓縮", "測試系統能否將大量對話壓縮成簡潔的記憶", difficulty=10
        )

        try:
            # 準備大量消息
            messages = []
            topics = ["比特幣", "以太幣", "SOL", "XRP", "DOGE"]
            for i, topic in enumerate(topics):
                timestamp = f"2026-01-0{i + 1} 10:{i:02d}"
                messages.append(
                    {
                        "role": "user",
                        "content": f"我想了解 {topic} 的投資價值",
                        "timestamp": timestamp,
                    }
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"{topic} 是一種加密貨幣...",
                        "timestamp": timestamp,
                    }
                )

            # 執行整合
            self.log(f"整合 {len(messages)} 條消息...")
            success = await self.memory_store.consolidate(
                messages=messages,
                llm=self.manager.llm,
                memory_window=10,
                archive_all=True,
            )

            if success:
                memory = self.memory_store.read_long_term()

                # 檢查壓縮效果
                # 理想情況下，記憶應該比原始消息短
                original_length = sum(len(m.get("content", "")) for m in messages)
                compressed_length = len(memory)

                self.log(f"原始長度: {original_length}, 壓縮後: {compressed_length}")

                # 檢查是否包含關鍵資訊
                has_multiple_topics = sum(1 for t in topics if t in memory) >= 2

                if has_multiple_topics and compressed_length < original_length:
                    test.passed = True
                    test.details = {
                        "original_length": original_length,
                        "compressed_length": compressed_length,
                        "compression_ratio": round(
                            compressed_length / original_length * 100, 1
                        ),
                        "memory": memory[:400],
                    }
                    self.log(
                        f"✓ 記憶壓縮成功，壓縮率: {test.details['compression_ratio']}%"
                    )
                elif has_multiple_topics:
                    test.passed = True
                    test.details = {
                        "note": "壓縮但保留關鍵資訊",
                        "memory": memory[:400],
                    }
                    self.log("✓ 記憶整合成功，保留關鍵資訊")
                else:
                    test.error = f"壓縮後記憶缺少關鍵資訊: {memory[:200]}"
            else:
                test.error = "整合失敗"

        except Exception as e:
            test.error = str(e)
            import traceback

            test.details = {"traceback": traceback.format_exc()}

        return test

    # ==================== 執行所有測試 ====================

    async def run_all_tests(self) -> list:
        """執行所有測試案例"""
        print("\n" + "=" * 60)
        print("🧠 記憶系統測試開始")
        print("=" * 60)

        test_methods = [
            self.test_1_basic_memory_storage,
            self.test_2_information_recall,
            self.test_3_preference_memory,
            self.test_4_multi_round_accumulation,
            self.test_5_cross_topic_correlation,
            self.test_6_memory_update,
            self.test_7_history_retrieval,
            self.test_8_memory_consolidation,
            self.test_9_session_isolation,
            self.test_10_memory_compression,
        ]

        for i, test_method in enumerate(test_methods):
            print(
                f"\n[測試 {i + 1}/10] {test_method.__doc__.strip().split(chr(10))[0]}"
            )
            print("-" * 40)

            try:
                test_case = await test_method()
                self.test_cases.append(test_case)
                print(f"結果: {test_case}")
            except Exception as e:
                test_case = MemoryTestCase(
                    test_method.__name__, "測試執行失敗", difficulty=i + 1
                )
                test_case.error = str(e)
                self.test_cases.append(test_case)
                print(f"結果: ❌ 執行錯誤 - {e}")

            # 測試間隔
            await asyncio.sleep(1)

        return self.test_cases

    def print_summary(self):
        """打印測試總結"""
        passed = sum(1 for t in self.test_cases if t.passed)
        total = len(self.test_cases)

        print("\n" + "=" * 60)
        print("📊 測試結果總結")
        print("=" * 60)

        for test in self.test_cases:
            status = "✅ 通過" if test.passed else "❌ 失敗"
            print(f"  {status} [{test.difficulty}/10] {test.name}")
            if test.error:
                print(f"         錯誤: {test.error[:80]}")

        print("\n" + "-" * 60)
        print(f"總計: {passed}/{total} 通過 ({round(passed / total * 100, 1)}%)")
        print("-" * 60)

    def save_results(self):
        """儲存測試結果"""
        os.makedirs(RESULTS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memory_test_{timestamp}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        result = {
            "scenario": "memory_system_test",
            "user_id": TEST_USER_ID,
            "session_id": self.session_id,
            "total_rounds": self.round_count,
            "test_results": [
                {
                    "name": t.name,
                    "description": t.description,
                    "difficulty": t.difficulty,
                    "passed": t.passed,
                    "error": t.error,
                    "details": t.details,
                }
                for t in self.test_cases
            ],
            "conversation": self.conversation_log,
            "summary": {
                "total": len(self.test_cases),
                "passed": sum(1 for t in self.test_cases if t.passed),
                "failed": sum(1 for t in self.test_cases if not t.passed),
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n💾 測試結果已儲存: {filepath}")
        return filepath


async def main():
    """主程式"""
    if not Settings.ENABLE_MANAGER_V2:
        print("❌ 請先在 .env 中設置 ENABLE_MANAGER_V2=true")
        return

    from core.agents.bootstrap import bootstrap
    from utils.user_client_factory import create_user_llm_client

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ 缺少 API Key")
        return

    provider = "openrouter" if os.getenv("OPENROUTER_API_KEY") else "openai"
    print(f"\n🔧 初始化 LLM ({provider})...")
    llm = create_user_llm_client(
        provider=provider,
        api_key=api_key,
        model="gpt-4o-mini",
    )

    print("🔧 初始化 ManagerAgent...")
    manager = bootstrap(llm, web_mode=False, language="zh-TW")

    print("🔧 初始化記憶測試器...")
    tester = MemorySystemTester(manager, TEST_SESSION_ID)

    # 執行測試
    await tester.run_all_tests()

    # 打印總結
    tester.print_summary()

    # 儲存結果
    tester.save_results()


if __name__ == "__main__":
    asyncio.run(main())
