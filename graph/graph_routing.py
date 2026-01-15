"""
Graph 路由邏輯模組
定義所有節點之間的路由條件
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from typing import Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class FullState(BaseModel):
    """完整的 State 定義"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    query_type: str = ""
    knowledge: str = ""
    current_query: str = ""
    memory_summary: str = ""
    memory_response: str = ""
    memory_source: str = ""
    final_answer: str = ""
    validation_result: str = ""
    validation_feedback: str = ""
    retry_count: int = 0
    query_type_history: list = []
    knowledge_retrieval_count: int = 0
    validation_need_supplement_info: str = ""
    suggested_sub_questions: list = []  # 守門員建議的子問題（已棄用，改用 retrieval_steps）
    question_category: str = ""
    question_type_reasoning: str = ""  # 新增：問題類型判斷的 reasoning
    iteration_count: int = 0  # 新增：追蹤迭代次數，防止無限循環
    used_sources_dict: dict = {}  # 新增:追蹤使用到的參考文獻及其線索
    original_docs_dict: dict = {}  # 新增:追蹤使用到的參考文獻的原始完整內容
    matched_table_images: list = []  # 🆕 新增：匹配到的表格圖片列表 [{'table_file': str, 'image_path': str, 'title': str, 'page': int, 'similarity': float}]
    matched_educational_images: list = []  # 🆕 新增：匹配到的衛教圖片列表 [{'filename': str, 'image_path': str, 'health_topic': str, 'score': float}]
    context: Dict[str, Any] = {}  # 新增：用於 SummarizationNode 追蹤摘要狀態
    # Planning 相關欄位
    planning_result: Optional[dict] = None  # Planning 結果 (QueryPlanningResult)
    retrieval_steps: list = []  # 檢索步驟列表 [{'step': int, 'query': str, 'purpose': str}]
    current_step: int = 0  # 當前執行到第幾步 (從0開始,0表示還沒開始分步)
    # 控制參數
    enable_short_term_memory: bool = False  # 🔧 是否啟用短期記憶（對話歷史）- 預設停用，以保持向後兼容
    enable_long_term_memory: bool = False  # 是否啟用長期記憶（mem0）
    datasource_ids: Optional[list[str]] = None  # 指定使用的資料源 ID 列表
    enabled_tool_ids: Optional[list[str]] = None  # 指定啟用的工具 ID 列表，None=使用配置預設值


def route_after_memory(state: FullState):
    """記憶檢索後的路由（問題精確化後直接進入分類）"""
    print(f"🔀 [路由] route_after_memory - 迭代次數: {state.iteration_count}/20")

    # ⚠️ 優先檢查迭代次數
    if state.iteration_count > 19:
        print(f"⚠️ 迭代次數已達上限 ({state.iteration_count}/20)，返回罐頭訊息")
        return "set_out_of_scope_message"

    print("⏭️ 進入分類流程 → classify_query_type")
    return "classify_query_type"


def route_after_classification(state: FullState):
    """分類後的路由"""
    # ⚠️ 優先檢查迭代次數（使用 > 19 來確保在達到 20 之前就停止）
    if state.iteration_count > 19:
        print(f"⚠️ 迭代次數已達上限 ({state.iteration_count}/20)，返回罐頭訊息")
        return "set_out_of_scope_message"

    query_type = state.query_type

    if query_type in ["greet", "out_of_scope"]:
        print(f"✅ 查詢類型: {query_type}，直接生成回答")
        return "generate_response"
    else:
        print(f"✅ 查詢類型: {query_type}，需要檢索知識")
        return "retrieve_knowledge"


def route_after_generate(state: FullState):
    """生成回答後的路由"""
    # ⚠️ 優先檢查迭代次數（使用 > 19 來確保在達到 20 之前就停止）
    if state.iteration_count > 19:
        print(f"⚠️ 迭代次數已達上限 ({state.iteration_count}/20)，返回罐頭訊息")
        return "set_out_of_scope_message"

    query_type = state.query_type

    # 問候、超出範圍 → 直接結束
    if query_type in ["greet", "out_of_scope"]:
        print("✅ 非醫療問題，直接結束")
        return "END"

    # 其他類型 → 檢查問題類別
    print("✅ 醫療問題，進入問題類別檢查")
    return "check_question_type"


def route_after_check_question_type(state: FullState):
    """檢查問題類別後的路由"""
    # ⚠️ 優先檢查迭代次數（使用 > 19 來確保在達到 20 之前就停止）
    if state.iteration_count > 19:
        print(f"⚠️ 迭代次數已達上限 ({state.iteration_count}/20)，返回罐頭訊息")
        return "set_out_of_scope_message"

    question_category = state.question_category

    # 如果是「回顧歷史」或「其他」，跳過驗證
    if question_category in ["conversation_history", "other"]:
        print(f"✅ 問題類別: {question_category}，跳過驗證")
        return "END"

    # 醫療問題 → 進入驗證
    print(f"✅ 問題類別: {question_category}，進入驗證")
    return "validate_answer"


def route_after_validation(state: FullState):
    """驗證後的路由"""
    validation_result = state.validation_result
    retry_count = state.retry_count
    knowledge_retrieval_count = state.knowledge_retrieval_count
    iteration_count = state.iteration_count
    MAX_RETRY_COUNT = 3
    MAX_KNOWLEDGE_RETRIEVAL_COUNT = 20
    MAX_ITERATION_COUNT = 19  # 修改：最大迭代次數限制（使用 19 來確保在達到 20 之前就停止）

    print(f"🔀 [路由] route_after_validation - 迭代次數: {iteration_count}/20, 檢索次數: {knowledge_retrieval_count}, 重試次數: {retry_count}")
    print(f"    驗證結果: {validation_result}")

    # ⚠️ 優先檢查：迭代次數超限 → 返回罐頭訊息
    if iteration_count > MAX_ITERATION_COUNT:
        print(f"⚠️ 迭代次數已達安全上限 ({iteration_count}/{MAX_ITERATION_COUNT+1})，避免觸發 recursion limit → set_out_of_scope_message")
        return "set_out_of_scope_message"

    # 通過驗證 → 結束
    if validation_result == "pass":
        print("✅ 驗證通過 → END")
        return "END"

    # 超出範圍（迭代次數或檢索次數達上限）→ 返回罐頭訊息
    if validation_result == "out_of_scope":
        print("⚠️ 驗證判定為超出範圍（資源耗盡）→ set_out_of_scope_message")
        return "set_out_of_scope_message"

    # 需要補充知識
    if validation_result == "need_more_knowledge":
        # 檢索次數超限 → 返回罐頭訊息
        if knowledge_retrieval_count >= MAX_KNOWLEDGE_RETRIEVAL_COUNT:
            print(f"⚠️ 知識檢索次數已達上限 ({MAX_KNOWLEDGE_RETRIEVAL_COUNT}) → set_out_of_scope_message")
            return "set_out_of_scope_message"

        print(f"🔄 需要補充知識，重新檢索 (次數: {knowledge_retrieval_count + 1}/{MAX_KNOWLEDGE_RETRIEVAL_COUNT}) → retrieve_knowledge")
        return "retrieve_knowledge"

    # 需要重新生成 → 精煉答案
    if validation_result == "regenerate":
        # 重試次數超限 → 改為返回罐頭訊息，避免輸出幻覺答案
        if retry_count >= MAX_RETRY_COUNT:
            print(f"⚠️ 重試次數已達上限 ({MAX_RETRY_COUNT})，無法生成可靠答案 → set_out_of_scope_message")
            return "set_out_of_scope_message"

        print(f"🔄 答案品質不佳，精煉答案 (重試: {retry_count + 1}/{MAX_RETRY_COUNT}) → refine_answer")
        return "refine_answer"

    # 預設：結束
    print(f"⚠️ 未知的驗證結果: {validation_result} → END")
    return "END"
