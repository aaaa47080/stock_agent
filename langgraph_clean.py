"""
主程式 - 簡化版（模組化後）
使用統一記憶管理器整合三層記憶架構
整合 Langfuse 追蹤功能
"""

import asyncio
import json
import opencc
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from graph.graph_nodes import memory_client
from core.prompt_config import MEMORY_DEDUCTION_PROMPT
# 導入配置
from core.config import (
    llm, WORKFLOW_LIMITS, SHORT_TERM_MEMORY_CONFIG,
    MESSAGE_SUMMARIZATION_CONFIG, RETRIEVAL_CONFIG, TOOLS_CONFIG,
    LONG_TERM_MEMORY_CONFIG, MEMORY_MANAGEMENT_CONFIG
)

# 初始化 OpenCC 轉換器 (簡體 -> 繁體)
converter = opencc.OpenCC('s2tw.json')

# 導入 Langfuse 追蹤
from monitoring.langfuse_integration import get_langfuse_config, update_trace_io

# 🆕 導入快取和記憶體管理
from utils.cache_manager import get_cache_manager, MemoryManager

# 導入 langmem 的 SummarizationNode
from langmem.short_term import SummarizationNode
from langchain_core.messages.utils import count_tokens_approximately

# 導入記憶系統
# from mem0 import Memory
# from long_term_memory import create_long_term_memory
# from memory_utils import create_unified_memory_manager

# 導入模組化的組件
from graph.graph_routing import (
    FullState,
    route_after_memory,
    route_after_classification,
    route_after_generate,
    route_after_check_question_type,
    route_after_validation
)

# 導入節點函數
from graph.graph_nodes import (
    extract_current_query,
    retrieve_memory,
    answer_from_memory,
    classify_query_type,
    planning_node,  # 新增：Planning 節點
    retrieve_knowledge,
    supplement_with_realtime_info,  # 即時搜尋補充節點（由使用者選擇是否啟用）
    generate_response,
    validate_answer,
    refine_answer,
    check_question_type,
    set_out_of_scope_message
)



# ===== 初始化快取和記憶體管理系統 =====
# print("\n" + "="*60)
# print("🔧 初始化快取和記憶體管理系統...")
# print("="*60)

# 獲取單例快取管理器
cache_manager = get_cache_manager()
if not cache_manager:
    # print("⏭️ 快取系統已停用")
    pass

# 初始化記憶體管理器
memory_manager = MemoryManager(MEMORY_MANAGEMENT_CONFIG)

# print("="*60 + "\n")

# ===== 初始化工具系統 =====
from tools_init import initialize_all_tools, get_active_tools

# 根據配置初始化工具系統
active_tools = []
if TOOLS_CONFIG.get('enabled', True):
    try:
        # print("\n" + "="*60)
        # print("🔧 初始化工具系統...")
        # print("="*60)
        initialize_all_tools()
        active_tools = get_active_tools()
        # if active_tools:
        #     print(f"\n✅ 工具系統已啟用，載入 {len(active_tools)} 個工具")
        # else:
        #     print(f"\n⚠️ 工具系統已啟用，但未載入任何工具")
        # print("="*60 + "\n")
    except Exception as e:
        print(f"\n⚠️ 工具系統初始化失敗: {e}")
        print("系統將繼續運行，但工具功能將不可用\n")
        active_tools = []
else:
    # print("\n⏭️ 工具系統已停用（可在 config.py 的 TOOLS_CONFIG 中啟用）\n")
    pass

# ===== 構建 Graph =====
# print("🔧 構建 LangGraph...")

# 短期記憶（當前會話）
checkpointer = InMemorySaver()

# ===== 配置 SummarizationNode（如果啟用）===== 
summarization_node = None
if MESSAGE_SUMMARIZATION_CONFIG.get('enabled', True):
    # print("✅ 啟用 Message Summarization")
    # 創建用於摘要的 LLM（綁定 max_tokens 以控制摘要長度）
    summarization_model = llm.bind(max_tokens=MESSAGE_SUMMARIZATION_CONFIG['max_summary_tokens'])

    # 創建 SummarizationNode
    summarization_node = SummarizationNode(
        token_counter=count_tokens_approximately,
        model=summarization_model,
        max_tokens=MESSAGE_SUMMARIZATION_CONFIG['max_tokens'],
        max_tokens_before_summary=MESSAGE_SUMMARIZATION_CONFIG['max_tokens_before_summary'],
        max_summary_tokens=MESSAGE_SUMMARIZATION_CONFIG['max_summary_tokens'],
        input_messages_key="messages",
        output_messages_key="messages",  # 🔑 關鍵：設為 "messages" 以替換原消息列表
    )
    # print(f"📊 摘要配置: max_tokens={MESSAGE_SUMMARIZATION_CONFIG['max_tokens']}, "
    #       f"觸發閾值={MESSAGE_SUMMARIZATION_CONFIG['max_tokens_before_summary']}")
else:
    # print("⏭️ Message Summarization 已停用")
    pass

# 創建 Graph
graph = StateGraph(FullState)

# 添加節點
graph.add_node("extract_current_query", extract_current_query)
graph.add_node("retrieve_memory", retrieve_memory)
graph.add_node("answer_from_memory", answer_from_memory)
graph.add_node("classify_query_type", classify_query_type)
graph.add_node("planning", planning_node)  # 🆕 Planning 節點
graph.add_node("retrieve_knowledge", retrieve_knowledge)
graph.add_node("supplement_realtime", supplement_with_realtime_info)  # 即時搜尋補充（由使用者透過 enabled_tool_ids 控制）
graph.add_node("generate_response", generate_response)
graph.add_node("validate_answer", validate_answer)
graph.add_node("refine_answer", refine_answer)
graph.add_node("check_question_type", check_question_type)
graph.add_node("set_out_of_scope_message", set_out_of_scope_message)

# 如果啟用 summarization，添加 summarization 節點
if summarization_node:
    graph.add_node("summarize", summarization_node)
    # print("✅ 已添加 'summarize' 節點到 Graph")

# 定義邊
# 如果啟用 summarization，在進入主流程前先經過摘要節點
if summarization_node:
    graph.add_edge(START, "summarize")
    graph.add_edge("summarize", "extract_current_query")
    # print("✅ 流程: START → summarize → extract_current_query")
else:
    graph.add_edge(START, "extract_current_query")
    # print("✅ 流程: START → extract_current_query")
graph.add_edge("extract_current_query", "retrieve_memory")
graph.add_edge("retrieve_memory", "answer_from_memory")

# 條件路由
graph.add_conditional_edges(
    "answer_from_memory",
    route_after_memory,
    {
        "classify_query_type": "classify_query_type",
        "set_out_of_scope_message": "set_out_of_scope_message"
    }
)
graph.add_conditional_edges(
    "classify_query_type",
    route_after_classification,
    {
        "retrieve_knowledge": "planning",  # 🆕 改為先進入 Planning
        "generate_response": "generate_response",
        "set_out_of_scope_message": "set_out_of_scope_message"
    }
)
# 🆕 Planning 後直接進入檢索
graph.add_edge("planning", "retrieve_knowledge")
# 工作流程：retrieve_knowledge → supplement_realtime → generate_response
# supplement_realtime 節點會根據使用者選擇的 enabled_tool_ids 決定是否使用外部搜尋
graph.add_edge("retrieve_knowledge", "supplement_realtime")
graph.add_edge("supplement_realtime", "generate_response")
graph.add_conditional_edges(
    "generate_response",
    route_after_generate,
    {
        "check_question_type": "check_question_type",
        "set_out_of_scope_message": "set_out_of_scope_message",
        "END": END
    }
)
graph.add_conditional_edges(
    "check_question_type",
    route_after_check_question_type,
    {
        "validate_answer": "validate_answer",
        "set_out_of_scope_message": "set_out_of_scope_message",
        "END": END
    }
)
graph.add_conditional_edges(
    "validate_answer",
    route_after_validation,
    {
        "refine_answer": "refine_answer",
        "retrieve_knowledge": "retrieve_knowledge",
        "set_out_of_scope_message": "set_out_of_scope_message",
        "END": END
    }
)
graph.add_edge("refine_answer", "validate_answer")
graph.add_edge("set_out_of_scope_message", END)

# 編譯
app = graph.compile(checkpointer=checkpointer)

# print("✅ LangGraph 構建完成\n")


# ===== 對話歷史管理 =====
conversation_history = []

def display_conversation_history():
    """顯示對話歷史"""
    if not conversation_history:
        print("\n📋 目前沒有對話歷史\n")
        return

    print("\n" + "=" * 80)
    print("📋 對話歷史")
    print("=" * 80)
    for i, (query, answer) in enumerate(conversation_history, 1):
        print(f"\n[{i}] 👤 用戶: {query[:50]}..." if len(query) > 50 else f"\n[{i}] 👤 用戶: {query}")
        print(f"    🤖 系統: {answer[:50]}..." if len(answer) > 50 else f"    🤖 系統: {answer}")
    print("=" * 80 + "\n")


def display_help():
    """顯示幫助信息"""
    print("\n" + "=" * 80)
    print("📖 可用指令")
    print("=" * 80)
    print("  /help     - 顯示此幫助信息")
    print("  /history  - 顯示對話歷史")
    print("  /clear    - 清除對話歷史和快取")
    print("  /stats    - 🆕 顯示快取與記憶體統計")
    print("  /quit     - 退出系統")
    print("  /exit     - 退出系統")
    print("=" * 80 + "\n")


# ===== 主程式入口 =====
async def main():
    """主程式 - 連續對話版本"""
    global conversation_history  # 🔧 修正：宣告使用全域變數

    print("\n" + "=" * 80)
    print("🏥 醫療諮詢系統已啟動（連續對話版本 + 三層記憶）")
    print("=" * 80)
    print("💡 輸入 /help 查看可用指令")
    print("=" * 80 + "\n")

    user_id = "test_user_00100100"
    session_id = "conversation_006"
    # 使用 user_id + session_id 組合確保不同用戶的會話完全隔離
    thread_id = f"{user_id}_{session_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # 連續對話循環
    while True:
        try:
            # 獲取用戶輸入
            query = input("\n👤 請輸入您的問題（或輸入指令）: ").strip()

            # 處理空輸入
            if not query:
                print("⚠️  請輸入有效的問題或指令")
                continue

            # 處理系統指令
            if query.startswith("/"):
                if query in ["/quit", "/exit"]:
                    print("\n👋 感謝使用醫療諮詢系統，再見！\n")
                    break
                elif query == "/help":
                    display_help()
                    continue
                elif query == "/history":
                    display_conversation_history()
                    continue
                elif query == "/clear":
                    conversation_history.clear()

                    # 🆕 清除快取
                    if cache_manager:
                        cache_manager.clear_all()

                    # 根據配置決定是否清除長期記憶
                    if LONG_TERM_MEMORY_CONFIG.get('enabled', True):
                        memory_client.delete_all(user_id=user_id)
                        print("\n✅ 對話歷史、快取和長期記憶已清除\n")
                    else:
                        print("\n✅ 對話歷史和快取已清除（長期記憶已停用）\n")
                    continue
                elif query == "/stats":
                    # 🆕 顯示快取和記憶體統計
                    if cache_manager:
                        cache_manager.print_stats()
                    memory_manager.print_memory_info(conversation_history)
                    continue
                else:
                    print(f"❌ 未知指令: {query}")
                    print("💡 輸入 /help 查看可用指令\n")
                    continue

            # 處理正常問題
            # print(f"\n{ '='*80}")
            # print(f"🔍 正在處理您的問題...")
            # print(f"{ '='*80}\n")

            # 獲取 Langfuse 配置
            # session_id (thread_id) 用於在 Langfuse 中分組同一會話的所有對話
            # 每次調用 CallbackHandler 會自動創建新的 trace
            langfuse_cfg, langfuse_handler = get_langfuse_config(
                user_id=user_id,
                session_id=thread_id,  # 使用 thread_id 作為 session_id,而不是每次生成新的
                tags=["cli", "medical", "rag"],
                metadata={
                    "query": query,
                    "source": "cli",
                    "short_term_memory_enabled": SHORT_TERM_MEMORY_CONFIG.get('enabled', False),
                    "long_term_memory_enabled": LONG_TERM_MEMORY_CONFIG.get('enabled', False),
                    "datasource_ids": RETRIEVAL_CONFIG.get('default_datasource_ids')
                }
            )

            # 構建 messages 列表
            messages = []
            if SHORT_TERM_MEMORY_CONFIG.get('enabled', True):
                for user_q, asst_a in conversation_history:
                    messages.append(HumanMessage(content=user_q))
                    messages.append(AIMessage(content=asst_a))

            # 添加當前用戶問題
            messages.append(HumanMessage(content=query))

            # 構建 state
            initial_state = {
                "messages": messages,
                "user_id": user_id,
                "query_type": "",
                "knowledge": "",
                "current_query": "",
                "memory_summary": "",
                "memory_response": "",
                "memory_source": "",
                "final_answer": "",
                "validation_result": "",
                "validation_feedback": "",
                "retry_count": 0,
                "query_type_history": [],
                "knowledge_retrieval_count": 0,
                "validation_need_supplement_info": "",
                "question_category": "",
                "iteration_count": 0,
                "used_sources_dict": {},
                "planning_result": None,  # 🆕 Planning 結果
                "retrieval_steps": [],  # 🆕 檢索步驟
                "current_step": 0,  # 🆕 當前步驟
                "enable_short_term_memory": SHORT_TERM_MEMORY_CONFIG.get('enabled', False),
                "datasource_ids": RETRIEVAL_CONFIG.get('default_datasource_ids'),
                "enabled_tool_ids": TOOLS_CONFIG.get('default_tools')  # 🆕 確保 CDC 搜尋工具被啟用
            }

            # 運行 graph
            config_with_limit = {
                **config,
                "recursion_limit": WORKFLOW_LIMITS["langgraph_recursion_limit"],
                **langfuse_cfg
            }
            result = await app.ainvoke(initial_state, config_with_limit)

            # 獲取回答
            answer = result.get("final_answer", "抱歉，無法生成回答")
            
            # 使用 OpenCC 將回答轉換為繁體中文 (針對 OCR 可能產生的簡體中文)
            if answer:
                answer = converter.convert(answer)
                
            query_type = result.get("query_type", "")

            # 更新 trace
            if langfuse_handler:
                update_trace_io(
                    handler=langfuse_handler,
                    user_query=query,
                    final_answer=answer,
                    additional_metadata={"query_type": query_type}
                )


            # 保存到記憶
            should_save_to_memory = (
                query_type not in ["greet", "out_of_scope", "conversation_history"] and
                answer not in [
                    "抱歉，這個問題超出了我的專業範圍。",
                    "抱歉，這個問題超出了我的專業範圍。我專注於提供醫療感染管制相關的諮詢服務。",
                    "抱歉，您的問題超出了我的認知範圍，請您換個方式再提問一次，或者聯絡相關專業人員為您服務。",
                    "抱歉，資料庫中未找到可回答此問題的醫療資訊。請諮詢專業醫療人員或相關科室。",
                    "抱歉，無法生成回答",
                    "抱歉，生成回答時發生錯誤。"
                ]
            )

            if should_save_to_memory:
                if LONG_TERM_MEMORY_CONFIG.get('enabled', True):
                    try:
                        # print("\n" + "="*80)
                        # print("💾 【長期記憶儲存】開始")
                        # print("="*80)

                        clean_answer_for_memory = answer
                        if "**參考依據**" in clean_answer_for_memory:
                            clean_answer_for_memory = clean_answer_for_memory[:clean_answer_for_memory.find("**參考依據**")].rstrip()
                        if "**相關表格**" in clean_answer_for_memory:
                            clean_answer_for_memory = clean_answer_for_memory[:clean_answer_for_memory.find("**相關表格**")].rstrip()

                        qa_pair = f"用戶問題：{query}\n助手回答：{clean_answer_for_memory}"

                        # print(f"👤 用戶 ID: {user_id}")
                        # print(f"📝 儲存內容長度: {len(qa_pair)} 字元")
                        # print("-"*80)
                        # print("📄 儲存內容預覽:")
                        # print(qa_pair[:200] + "..." if len(qa_pair) > 200 else qa_pair)
                        # print("-"*80)

                        add_result = memory_client.add(
                            qa_pair,
                            user_id=user_id,
                            metadata={"category": "medical_chat"},
                            prompt=MEMORY_DEDUCTION_PROMPT
                        )

                        # print("\n📦 儲存結果:")
                        # print(json.dumps(add_result, ensure_ascii=False, indent=2))
                        # print("="*80)
                        # print("✅ 已成功儲存到長期記憶（mem0）")
                        # print("="*80 + "\n")
                    except Exception as e:
                        print(f"\n❌ 長期記憶儲存失敗: {e}")
                        import traceback
                        traceback.print_exc()
                        print("="*80 + "\n")
                else:
                    # print("⏭️ 跳過長期記憶儲存（已停用）")
                    pass

            if should_save_to_memory:
                if SHORT_TERM_MEMORY_CONFIG.get('enabled', True):
                    clean_answer = answer
                    if "**參考依據**" in clean_answer:
                        clean_answer = clean_answer[:clean_answer.find("**參考依據**")].rstrip()
                    if "**相關表格**" in clean_answer:
                        clean_answer = clean_answer[:clean_answer.find("**相關表格**")].rstrip()
                    conversation_history.append((query, clean_answer))
                    # print(f"💾 已儲存到短期記憶（對話歷史）- 移除參考文獻後 {len(clean_answer)} 字元")

                    # 🆕 自動清理對話歷史
                    conversation_history, removed = memory_manager.cleanup(conversation_history)
                    if removed > 0:
                        # print(f"   ⚠️ 記憶體管理：自動清理了 {removed} 輪舊對話")
                        pass
                else:
                    conversation_history.clear()
            else:
                # print(f"⏭️ 跳過記憶儲存（類型: {query_type or '未知'}）")
                if not SHORT_TERM_MEMORY_CONFIG.get('enabled', True):
                    conversation_history.clear()

            # 顯示結果
            print(f"\n{ '='*80}")
            print("🤖 系統回答:")
            print(f"{ '='*80}")
            print(answer)
            print(f"{ '='*80}\n")

        except KeyboardInterrupt:
            print("\n\n👋 檢測到中斷信號，正在退出...\n")
            break
        except Exception as e:
            print(f"\n❌ 發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            print("\n💡 您可以繼續提問或輸入 /quit 退出\n")


if __name__ == "__main__":
    asyncio.run(main())