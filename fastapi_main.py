"""FastAPI 後端 - 整合 Langfuse 追蹤"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import opencc
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

from core.dataclass import MedicalResponse

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from core.config import llm, WORKFLOW_LIMITS, SHORT_TERM_MEMORY_CONFIG, MESSAGE_SUMMARIZATION_CONFIG, LONG_TERM_MEMORY_CONFIG, RETRIEVAL_CONFIG, TOOLS_CONFIG
from core.prompt_config import MEMORY_DEDUCTION_PROMPT

# 初始化 OpenCC 轉換器 (簡體 -> 繁體)
converter = opencc.OpenCC('s2tw.json')

# 導入 Langfuse 追蹤
from monitoring.langfuse_integration import get_langfuse_config, update_trace_io

# 導入 langmem 的 SummarizationNode
from langmem.short_term import SummarizationNode
from langchain_core.messages.utils import count_tokens_approximately
from graph.graph_routing import (
    FullState,
    route_after_memory,
    route_after_classification,
    route_after_generate,
    route_after_check_question_type,
    route_after_validation
)
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
    set_out_of_scope_message,
    memory_client
)

# ===== 初始化工具系統 =====
from tools_init import initialize_all_tools, get_active_tools

app = FastAPI(title="醫療諮詢系統 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源,方便同網段用戶訪問
    allow_credentials=False,  # 設為 False 以支援 file:// 協議
    allow_methods=["*"],
    allow_headers=["*"],
)

checkpointer = InMemorySaver()

# ===== 初始化工具系統 =====
# 根據配置初始化工具系統
active_tools = []
if TOOLS_CONFIG.get('enabled', True):
    try:
        print("\n" + "="*60)
        print("🔧 初始化工具系統...")
        print("="*60)
        initialize_all_tools()
        active_tools = get_active_tools()
        if active_tools:
            print(f"\n✅ 工具系統已啟用，載入 {len(active_tools)} 個工具")
        else:
            print(f"\n⚠️ 工具系統已啟用，但未載入任何工具")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\n⚠️ 工具系統初始化失敗: {e}")
        print("系統將繼續運行，但工具功能將不可用\n")
        active_tools = []
else:
    print("\n⏭️ 工具系統已停用（可在 config.py 的 TOOLS_CONFIG 中啟用）\n")

# ===== 配置 SummarizationNode（如果啟用）=====
summarization_node = None
if MESSAGE_SUMMARIZATION_CONFIG.get('enabled', True):
    print("✅ 啟用 Message Summarization")
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
    print(f"📊 摘要配置: max_tokens={MESSAGE_SUMMARIZATION_CONFIG['max_tokens']}, "
          f"觸發閾值={MESSAGE_SUMMARIZATION_CONFIG['max_tokens_before_summary']}")
else:
    print("⏭️ Message Summarization 已停用")

graph = StateGraph(FullState)

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
    print("✅ 已添加 'summarize' 節點到 Graph")

# 定義邊
# 如果啟用 summarization，在進入主流程前先經過摘要節點
if summarization_node:
    graph.add_edge(START, "summarize")
    graph.add_edge("summarize", "extract_current_query")
    print("✅ 流程: START → summarize → extract_current_query")
else:
    graph.add_edge(START, "extract_current_query")
    print("✅ 流程: START → extract_current_query")
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

langgraph_app = graph.compile(checkpointer=checkpointer)

class ChatRequest(BaseModel):
    """
    聊天請求參數

    必填參數：
    - user_id: 用戶唯一識別碼（用於隔離不同用戶的快取和記憶）
    - message: 用戶問題

    可選參數：
    - session_id: 對話會話 ID（用於追蹤同一對話的多輪問答）
    - enable_short_term_memory: 是否啟用短期記憶（對話歷史）
    - enable_long_term_memory: 是否啟用長期記憶（mem0 個人病史）
    - datasource_ids: 指定要使用的資料源（知識庫）列表
    - enabled_tool_ids: 指定要使用的外部工具（如 CDC 即時搜尋）列表
    """
    user_id: str
    message: str
    session_id: Optional[str] = "default_session"

    # 記憶控制參數
    enable_short_term_memory: Optional[bool] = False  # 短期記憶（對話歷史）
    enable_long_term_memory: Optional[bool] = False  # 長期記憶（個人病史）

    # 資料源控制參數（可用選項見 GET /api/config）
    datasource_ids: Optional[list[str]] = None  # None = 使用系統預設

    # 工具控制參數（可用選項見 GET /api/config）
    enabled_tool_ids: Optional[list[str]] = None  # None = 使用系統預設

def create_sse_message(event_type: str, content: str) -> str:
    data = {"type": event_type, "content": content}
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

conversation_store = {}

@app.get("/")
async def root():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/test", response_class=HTMLResponse)
async def test_page():
    """提供測試頁面"""
    import os
    html_path = os.path.join(os.path.dirname(__file__), "test_chat.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/config")
async def get_api_config():
    """
    獲取 API 可用的配置選項

    返回：
    - datasources: 可用的資料源（知識庫）列表
    - tools: 可用的外部工具列表
    - memory_options: 記憶系統配置選項
    - default_settings: 系統預設設定
    """
    from core.datasource_config import get_registry
    from tools_config import get_all_tools

    # 獲取所有可用的資料源
    registry = get_registry()
    all_datasources = registry.get_all()
    enabled_datasources = registry.get_enabled()

    datasources_info = [
        {
            "id": ds.id,
            "name": ds.name,
            "description": f"{ds.name} - {ds.source_type.upper()} 格式",
            "enabled": ds.enabled,
            "default_k": ds.default_k,
            "support_medical": ds.support_medical,
            "support_procedure": ds.support_procedure,
            "metadata": ds.metadata
        }
        for ds in all_datasources
    ]

    # 獲取所有可用的工具
    all_tools = get_all_tools()  # 返回 dict
    tools_info = [
        {
            "id": tool_config.id,
            "name": tool_config.name,
            "description": tool_config.description,
            "enabled": tool_config.enabled,
            "support_medical": tool_config.support_medical,
            "support_general": tool_config.support_general,
            "timeout": tool_config.timeout,
            "metadata": tool_config.metadata
        }
        for tool_config in all_tools.values()  # 迭代 dict 的 values
    ]

    return {
        "datasources": {
            "available": datasources_info,
            "enabled_ids": [ds.id for ds in enabled_datasources],
            "default_ids": RETRIEVAL_CONFIG.get('default_datasource_ids'),
            "description": "可用的知識庫資料源，可在請求中透過 datasource_ids 參數指定"
        },
        "tools": {
            "available": tools_info,
            "enabled_ids": [tool_config.id for tool_config in all_tools.values() if tool_config.enabled],
            "default_ids": TOOLS_CONFIG.get('default_tools'),
            "description": "可用的外部工具（如即時搜尋），可在請求中透過 enabled_tool_ids 參數指定"
        },
        "memory_options": {
            "short_term_memory": {
                "description": "短期記憶（對話歷史），保留當前會話的問答記錄",
                "default": SHORT_TERM_MEMORY_CONFIG.get('enabled', True),
                "privacy": "🔒 隔離：每個 session_id 獨立，不跨會話共享"
            },
            "long_term_memory": {
                "description": "長期記憶（個人病史），記錄用戶的健康資訊（如過敏史、病史）",
                "default": LONG_TERM_MEMORY_CONFIG.get('enabled', False),
                "privacy": "🔒 隔離：每個 user_id 獨立，不跨用戶共享",
                "note": "⚠️ 目前預設停用，如需使用請聯繫管理員"
            }
        },
        "privacy_protection": {
            "cache_strategy": {
                "query_cache": "完全隔離（包含 user_id）",
                "planning_cache": "完全隔離（包含 user_id）",
                "retrieval_cache": "主問題不快取，子問題可跨用戶共享（僅快取公開醫療知識）"
            },
            "description": "系統已實施三層快取隱私保護機制，確保用戶個人信息不會泄露"
        },
        "default_settings": {
            "enable_short_term_memory": True,
            "enable_long_term_memory": False,
            "datasource_ids": RETRIEVAL_CONFIG.get('default_datasource_ids'),
            "enabled_tool_ids": TOOLS_CONFIG.get('default_tools')
        }
    }

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """串流式聊天接口"""

    async def event_generator():
        try:
            # 準備對話歷史
            session_id = request.session_id
            if session_id not in conversation_store:
                conversation_store[session_id] = []

            # 獲取 Langfuse 配置

            langfuse_cfg, langfuse_handler = get_langfuse_config(
                user_id=request.user_id,
                session_id=session_id,  # 使用對話的 session_id
                tags=["fastapi", "stream", "medical", "rag"],
                metadata={
                    "query": request.message,
                    "source": "fastapi_stream",
                    "short_term_memory_enabled": request.enable_short_term_memory,
                    "long_term_memory_enabled": request.enable_long_term_memory,
                    "datasource_ids": request.datasource_ids,
                    "enabled_tool_ids": request.enabled_tool_ids
                }
            )

            # 構建 messages 列表

            messages = []

            # 檢查是否啟用短期記憶

            use_short_term_memory = request.enable_short_term_memory if request.enable_short_term_memory is not None else SHORT_TERM_MEMORY_CONFIG.get('enabled', True)
            if use_short_term_memory:
                for user_q, asst_a in conversation_store[session_id]:
                    messages.append(HumanMessage(content=user_q))

                    messages.append(AIMessage(content=asst_a))

            # 添加當前用戶問題

            messages.append(HumanMessage(content=request.message))

            # 構建 state

            initial_state = {
                "messages": messages,
                "user_id": request.user_id,
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
                "question_type_reasoning": "",
                "suggested_sub_questions": [],
                "iteration_count": 0,
                "used_sources_dict": {},
                "original_docs_dict": {},
                "matched_table_images": [],
                "matched_educational_images": [],  # 🆕 衛教圖片
                "context": {},
                "planning_result": None,  # 🆕 Planning 結果
                "retrieval_steps": [],  # 🆕 檢索步驟
                "current_step": 0,  # 🆕 當前步驟
                "enable_short_term_memory": use_short_term_memory,
                "enable_long_term_memory": request.enable_long_term_memory,
                "datasource_ids": request.datasource_ids if request.datasource_ids is not None else RETRIEVAL_CONFIG.get('default_datasource_ids'),
                "enabled_tool_ids": request.enabled_tool_ids if request.enabled_tool_ids is not None else TOOLS_CONFIG.get('default_tools')
            }

            # 運行 graph
            # 使用 user_id + session_id 組合確保不同用戶的會話完全隔離
            thread_id = f"{request.user_id}_{session_id}"
            config_with_limit = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": WORKFLOW_LIMITS["langgraph_recursion_limit"],
                **langfuse_cfg
            }

            current_query_type = None
            matched_table_images_buffer = []
            matched_educational_images_buffer = []  # 🆕 衛教圖片緩衝區

            final_answer_buffer = ""
            async for event in langgraph_app.astream(initial_state, config_with_limit):
                for node_name, node_output in event.items():
                    if node_name == "classify_query_type":
                        query_type = node_output.get("query_type", "")
                        if query_type:
                            current_query_type = query_type
                    if "final_answer" in node_output and node_output["final_answer"]:
                        final_answer_buffer = node_output["final_answer"]
                    if "matched_table_images" in node_output and node_output["matched_table_images"]:
                        matched_table_images_buffer = node_output["matched_table_images"]
                    # 🆕 捕獲衛教圖片
                    if "matched_educational_images" in node_output and node_output["matched_educational_images"]:
                        matched_educational_images_buffer = node_output["matched_educational_images"]
            if final_answer_buffer:
                # 使用 OpenCC 將回答轉換為繁體中文
                final_answer_buffer = converter.convert(final_answer_buffer)

                # 更新 trace

                if langfuse_handler:
                    update_trace_io(
                        handler=langfuse_handler,
                        user_query=request.message,
                        final_answer=final_answer_buffer,
                        additional_metadata={"query_type": current_query_type}
                    )

                # 保存到記憶

                should_save_to_memory = (
                    current_query_type not in ["greet", "out_of_scope", "conversation_history"] and
                    final_answer_buffer not in [
                        "抱歉，這個問題超出了我的專業範圍。",
                        "抱歉，這個問題超出了我的專業範圍。我專注於提供醫療感染管制相關的諮詢服務。",
                        "抱歉，您的問題超出了我的認知範圍，請您換個方式再提問一次，或者聯絡相關專業人員為您服務。",
                        "抱歉，資料庫中未找到可回答此問題的醫療資訊。請諮詢專業醫療人員或相關科室。",
                        "抱歉，無法生成回答",
                        "抱歉，生成回答時發生錯誤。"
                    ]
                )

                if should_save_to_memory:
                    use_long_term_memory = request.enable_long_term_memory if request.enable_long_term_memory is not None else LONG_TERM_MEMORY_CONFIG.get('enabled', False)
                    if use_long_term_memory:
                        try:
                            qa_pair = f"用戶問題：{request.message}\n助手回答：{final_answer_buffer}"

                            memory_client.add(
                                qa_pair,
                                user_id=request.user_id,
                                metadata={"category": "medical_chat"},
                                prompt=MEMORY_DEDUCTION_PROMPT
                            )

                        except Exception as e:
                            pass

                # 🔧 修正：將絕對路徑轉換為檔名
                import os
                processed_table_images = []
                for table in matched_table_images_buffer:
                    processed_table = table.copy()
                    if 'image_path' in processed_table and processed_table['image_path']:
                        processed_table['image_path'] = os.path.basename(processed_table['image_path'])
                    processed_table_images.append(processed_table)

                try:
                    medical_response = MedicalResponse.parse_from_text(final_answer_buffer, query_type=current_query_type)

                    yield create_sse_message("structured_data", json.dumps(medical_response.to_dict(), ensure_ascii=False))

                except Exception:
                    pass

                # 🆕 返回表格圖片資訊
                if processed_table_images:
                    yield create_sse_message("table_images", json.dumps(processed_table_images, ensure_ascii=False))

                # 🆕 返回衛教圖片資訊
                if matched_educational_images_buffer:
                    processed_edu_images = []
                    for img in matched_educational_images_buffer:
                        processed_edu_images.append({
                            'filename': img.get('filename', ''),
                            'image_path': img.get('image_path', ''),
                            'health_topic': img.get('health_topic', ''),
                            'core_message': img.get('core_message', ''),
                            'score': img.get('score', 0.0)
                        })
                    yield create_sse_message("educational_images", json.dumps(processed_edu_images, ensure_ascii=False))

                for char in final_answer_buffer:
                    yield create_sse_message("token", char)

                    await asyncio.sleep(0.005)

                if should_save_to_memory:
                    if use_short_term_memory:
                        conversation_store[session_id].append((request.message, final_answer_buffer))

            yield create_sse_message("done", "success")

        except Exception as e:
            yield create_sse_message("error", str(e))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        session_id = request.session_id
        if session_id not in conversation_store:
            conversation_store[session_id] = []

        # 獲取 Langfuse 配置
        # session_id 用於在 Langfuse 中分組同一會話的所有對話
        # 每次調用 CallbackHandler 會自動創建新的 trace
        langfuse_cfg, langfuse_handler = get_langfuse_config(
            user_id=request.user_id,
            session_id=session_id,  # 使用對話的 session_id,而不是每次生成新的
            tags=["fastapi", "chat", "medical", "rag"],
            metadata={
                "query": request.message,
                "source": "fastapi_chat",
                "short_term_memory_enabled": request.enable_short_term_memory,
                "long_term_memory_enabled": request.enable_long_term_memory,
                "datasource_ids": request.datasource_ids,
                "enabled_tool_ids": request.enabled_tool_ids
            }
        )

        # 構建 messages 列表
        messages = []

        # 檢查是否啟用短期記憶
        use_short_term_memory = request.enable_short_term_memory if request.enable_short_term_memory is not None else SHORT_TERM_MEMORY_CONFIG.get('enabled', True)
        if use_short_term_memory:
            for user_q, asst_a in conversation_store[session_id]:
                messages.append(HumanMessage(content=user_q))
                messages.append(AIMessage(content=asst_a))

        # 添加當前用戶問題
        messages.append(HumanMessage(content=request.message))
        initial_state = {
            "messages": messages,
            "user_id": request.user_id,
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
            "question_type_reasoning": "",
            "suggested_sub_questions": [],
            "iteration_count": 0,
            "used_sources_dict": {},
            "original_docs_dict": {},
            "matched_table_images": [],
            "matched_educational_images": [],  # 🆕 衛教圖片
            "context": {},
            "planning_result": None,  # 🆕 Planning 結果
            "retrieval_steps": [],  # 🆕 檢索步驟
            "current_step": 0,  # 🆕 當前步驟
            "enable_short_term_memory": use_short_term_memory,
            "enable_long_term_memory": request.enable_long_term_memory,
            "datasource_ids": request.datasource_ids if request.datasource_ids is not None else RETRIEVAL_CONFIG.get('default_datasource_ids'),
            "enabled_tool_ids": request.enabled_tool_ids if request.enabled_tool_ids is not None else TOOLS_CONFIG.get('default_tools')
        }
        # 運行 graph
        # 使用 user_id + session_id 組合確保不同用戶的會話完全隔離
        thread_id = f"{request.user_id}_{session_id}"
        config_with_limit = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": WORKFLOW_LIMITS["langgraph_recursion_limit"],
            **langfuse_cfg
        }
        result = await langgraph_app.ainvoke(initial_state, config_with_limit)
        answer = result.get("final_answer", "抱歉，無法生成回答")
        
        # 使用 OpenCC 將回答轉換為繁體中文
        if answer:
            answer = converter.convert(answer)

        query_type = result.get("query_type", "")

        # 更新 trace
        if langfuse_handler:
            update_trace_io(
                handler=langfuse_handler,
                user_query=request.message,
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
            use_long_term_memory = request.enable_long_term_memory if request.enable_long_term_memory is not None else LONG_TERM_MEMORY_CONFIG.get('enabled', False)
            if use_long_term_memory:
                try:
                    qa_pair = f"用戶問題：{request.message}\n助手回答：{answer}"
                    memory_client.add(
                        qa_pair,
                        user_id=request.user_id,
                        metadata={"category": "medical_chat"},
                        prompt=MEMORY_DEDUCTION_PROMPT
                    )
                except Exception as e:
                    pass

        if should_save_to_memory:
            if use_short_term_memory:
                conversation_store[session_id].append((request.message, answer))

        matched_table_images = result.get("matched_table_images", [])
        matched_educational_images = result.get("matched_educational_images", [])

        # 🔧 修正：將絕對路徑轉換為檔名，供前端使用 /api/table-image/{filename}
        # 同時過濾掉不需要的欄位（matched, table_content）
        import os
        processed_table_images = []
        for table in matched_table_images:
            # 只保留前端需要的欄位
            processed_table = {
                'image_path': os.path.basename(table.get('image_path', '')) if table.get('image_path') else '',
                'similarity': table.get('similarity', 1.0),
                'source': table.get('source', 'matching')
            }
            processed_table_images.append(processed_table)

        # 🆕 處理衛教圖片
        processed_edu_images = []
        for img in matched_educational_images:
            processed_edu_images.append({
                'filename': img.get('filename', ''),
                'image_path': img.get('image_path', ''),
                'health_topic': img.get('health_topic', ''),
                'core_message': img.get('core_message', ''),
                'score': img.get('score', 0.0)
            })

        try:
            medical_response = MedicalResponse.parse_from_text(answer, query_type=query_type)
            return {
                "status": "success",
                "answer": answer,
                "query_type": query_type,
                "structured_response": medical_response.to_dict(),
                "matched_table_images": processed_table_images,
                "matched_educational_images": processed_edu_images  # 🆕
            }
        except Exception:
            return {
                "status": "success",
                "answer": answer,
                "query_type": query_type,
                "matched_table_images": processed_table_images,
                "matched_educational_images": processed_edu_images  # 🆕
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memory/clear/short_term")
async def clear_short_term_memory(user_id: str):
    try:
        keys_to_delete = [k for k in conversation_store.keys() if k.startswith(user_id)]
        for key in keys_to_delete:
            del conversation_store[key]
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memory/clear/long_term")
async def clear_long_term_memory(user_id: str):
    try:
        from core.config import LONG_TERM_MEMORY_CONFIG
        if LONG_TERM_MEMORY_CONFIG.get('enabled', True):
            memory_client.delete_all(user_id=user_id)
            return {"status": "success", "message": "長期記憶已清除"}
        else:
            return {"status": "success", "message": "長期記憶已停用，無需清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memory/clear/all")
async def clear_all_memory(user_id: str):
    try:
        # 清除短期記憶
        keys_to_delete = [k for k in conversation_store.keys() if k.startswith(user_id)]
        for key in keys_to_delete:
            del conversation_store[key]

        # 根據配置決定是否清除長期記憶
        from core.config import LONG_TERM_MEMORY_CONFIG
        if LONG_TERM_MEMORY_CONFIG.get('enabled', True):
            memory_client.delete_all(user_id=user_id)
            return {"status": "success", "message": "所有記憶已清除"}
        else:
            return {"status": "success", "message": "短期記憶已清除（長期記憶已停用）"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/table-image/{filename}")
async def get_table_image(filename: str):
    """
    提供表格圖片服務

    Args:
        filename: 圖片檔名，例如 '國人膳食營養素參考攝取量_p10_t1.jpg'

    Returns:
        FileResponse: 圖片檔案

    Raises:
        HTTPException: 404 如果檔案不存在
    """
    import os

    # 表格目錄
    from core.config import EXTRACTED_TABLES_DIR

    print(f"\n🔍 DEBUG: 收到圖片請求 - filename = {filename}")

    # 驗證檔名（防止路徑遍歷攻擊）
    if ".." in filename or "/" in filename or "\\" in filename:
        print(f"❌ 無效的檔案名稱: {filename}")
        raise HTTPException(status_code=400, detail="無效的檔案名稱")

    # 只允許圖片檔案
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(status_code=400, detail="僅支援圖片檔案")

    # 搜尋檔案（支援子目錄）
    # 格式範例: 國人膳食營養素參考攝取量_p10_t1.jpg
    # 可能位於: extracted_tables/國人膳食營養素參考攝取量/國人膳食營養素參考攝取量_p10_t1.jpg

    # 嘗試 1: 直接在根目錄
    file_path = os.path.join(EXTRACTED_TABLES_DIR, filename)
    print(f"🔍 嘗試 1: {file_path}")
    if os.path.exists(file_path) and os.path.isfile(file_path):
        print(f"✅ 找到圖片（根目錄）: {file_path}")
        return FileResponse(
            file_path,
            media_type="image/jpeg" if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg') else "image/png",
            filename=filename
        )

    # 嘗試 2: 在統一的 images 資料夾中尋找
    images_path = os.path.join(EXTRACTED_TABLES_DIR, "images", filename)
    print(f"🔍 嘗試 2: {images_path}")
    if os.path.exists(images_path) and os.path.isfile(images_path):
        print(f"✅ 找到圖片（images 目錄）: {images_path}")
        return FileResponse(
            images_path,
            media_type="image/jpeg" if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg') else "image/png",
            filename=filename
        )

    # 嘗試 3: 遍歷所有子目錄搜尋
    print(f"🔍 嘗試 3: 遍歷所有子目錄...")
    for root, _, files in os.walk(EXTRACTED_TABLES_DIR):
        if filename in files:
            found_path = os.path.join(root, filename)
            print(f"✅ 找到圖片（遍歷）: {found_path}")
            return FileResponse(
                found_path,
                media_type="image/jpeg" if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg') else "image/png",
                filename=filename
            )

    # 找不到檔案
    print(f"❌ 找不到圖片: {filename}")
    raise HTTPException(status_code=404, detail=f"找不到圖片: {filename}")


@app.get("/api/educational-image/{filename}")
async def get_educational_image(filename: str):
    """
    提供衛教圖片服務

    Args:
        filename: 圖片檔名，例如 'B型肝炎衛教_p1_img1.jpg'

    Returns:
        FileResponse: 圖片檔案

    Raises:
        HTTPException: 404 如果檔案不存在
    """
    import os

    print(f"\n🔍 DEBUG: 收到衛教圖片請求 - filename = {filename}")

    # 驗證檔名（防止路徑遍歷攻擊）
    if ".." in filename or "/" in filename or "\\" in filename:
        print(f"❌ 無效的檔案名稱: {filename}")
        raise HTTPException(status_code=400, detail="無效的檔案名稱")

    # 只允許圖片檔案
    if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(status_code=400, detail="僅支援圖片檔案")

    # 衛教圖片目錄（從環境變數讀取，逗號分隔）
    import os
    image_dirs_env = os.getenv("IMAGE_DIRS", "/home/danny/AI-agent/high_value_images,/home/danny/AI-agent/image_search")
    possible_dirs = [d.strip() for d in image_dirs_env.split(",") if d.strip()]

    for base_dir in possible_dirs:
        # 嘗試直接在目錄中尋找
        file_path = os.path.join(base_dir, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            print(f"✅ 找到衛教圖片: {file_path}")
            return FileResponse(
                file_path,
                media_type="image/jpeg" if filename.lower().endswith(('.jpg', '.jpeg')) else "image/png",
                filename=filename
            )

        # 遍歷子目錄
        if os.path.exists(base_dir):
            for root, _, files in os.walk(base_dir):
                if filename in files:
                    found_path = os.path.join(root, filename)
                    print(f"✅ 找到衛教圖片（遍歷）: {found_path}")
                    return FileResponse(
                        found_path,
                        media_type="image/jpeg" if filename.lower().endswith(('.jpg', '.jpeg')) else "image/png",
                        filename=filename
                    )

    # 找不到檔案
    print(f"❌ 找不到衛教圖片: {filename}")
    raise HTTPException(status_code=404, detail=f"找不到衛教圖片: {filename}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="172.23.37.2", port=8100, log_level="info")
