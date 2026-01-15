"""
提示詞函數配置文件
提供動態生成提示詞的函數
"""

from core.prompt_config import (
    QUERY_CLASSIFICATION_PROMPT,
    RAG_RESPONSE_PROMPT,
    RAG_RESPONSE_WITH_HISTORY_PROMPT,
    CRITERIA_MATCHING_PROMPT,
    RAG_MULTI_SOURCE_SUMMARY_PROMPT,
    DISESE_CRITERIA
)


def get_query_classification_prompt(query: str, history_summary: str = "") -> str:
    """生成查詢分類提示詞"""
    return QUERY_CLASSIFICATION_PROMPT.format(
        history_summary=history_summary if history_summary else "無歷史記錄",
        query=query
    )


def get_rag_response_prompt(knowledge: str, question: str, question_reasoning: str = "") -> str:
    """生成基於 RAG 知識的回應提示詞（標準版）"""
    # 如果有問題分析結果，添加到 prompt 中
    reasoning_context = ""
    if question_reasoning:
        reasoning_context = f"\n\n【問題分析】\n系統分析：{question_reasoning}\n請在回答時考慮這個分析結果。"

    prompt = RAG_RESPONSE_PROMPT.format(knowledge=knowledge, question=question)
    return prompt + reasoning_context if reasoning_context else prompt


def get_rag_response_prompt_with_history(
    knowledge: str,
    question: str,
    memory_summary: str = "",
    conversation_context: str = "",
    question_reasoning: str = ""
) -> str:
    """生成基於 RAG 知識的回應提示詞（含歷史症狀關聯版）"""
    # 構建歷史症狀提示
    history_prompt = ""
    if memory_summary or conversation_context:
        history_prompt = f"""

    【個人疾病史】
    {memory_summary if memory_summary else ""}
    
    【對話上下文紀錄
    {conversation_context if conversation_context else ""}

    【整合歷史資訊的原則】
    - 只在確實有助於回答時，才自然地整合歷史症狀到綜合建議中
    - 避免突兀地說「您剛才還提到了...」或重複用戶已知的資訊
    - 若歷史症狀與當前問題無直接關聯，則不必提及
        """

    # 添加問題分析結果
    if question_reasoning:
        history_prompt += f"\n【問題分析】\n系統分析：{question_reasoning}\n請在回答時考慮這個分析結果。"

    return RAG_RESPONSE_WITH_HISTORY_PROMPT.format(
        knowledge=knowledge,
        question=question,
        history_prompt=history_prompt
    )


def get_criteria_matching_prompt() -> str:
    """醫療準則匹配提示詞"""
    return CRITERIA_MATCHING_PROMPT.format(criteria_list=DISESE_CRITERIA)


def get_system_prompt_for_multi_source(data_type: str) -> str:
    """獲取多來源摘要的系統提示詞（新版本：不整合）"""
    prompts = {
        "RAG_SEARCH": RAG_MULTI_SOURCE_SUMMARY_PROMPT
    }
    
    return prompts.get(data_type, """請將每筆資料分別整理，不要整合。

【輸出格式】
**參考依據**
《文件名稱1》-答案內容1（僅提取與問題相關的資訊）
《文件名稱2》-答案內容2（僅提取與問題相關的資訊）

""")


# def get_system_prompt_for_integrated_summary(data_type: str) -> str:
#     """獲取整合版摘要的系統提示詞（舊版本：會整合）"""
#     prompts = {
#         "RAG_SEARCH": RAG_SUMMARY_PROMPT
#     }
    
#     return prompts.get(data_type, """請整理資料中與問題相關的內容。
# 使用 **參考依據** 格式標註來源。
# """)