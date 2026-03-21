"""
Prompt Injection 防護與 JSON Schema 驗證

職責：
1. sanitize_user_input — 過濾常見 prompt injection 模式
2. validate_intent_response — 對意圖理解結果做基本 schema 驗證
3. validate_reflection_response — 對反思結果做基本 schema 驗證
4. parse_and_validate_json_response — 安全解析 + 驗證，失敗時回傳預設值

設計原則：
- 不要過度過濾，允許正常的加密貨幣/金融相關查詢
- 記錄被過濾的嘗試（audit trail）
- schema 驗證失敗時回傳安全預設值，不要拋錯
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt Injection 過濾規則
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: List[re.Pattern[str]] = [
    # 中文指令覆蓋
    re.compile(r"忽略.*(?:規則|指令|instruction|rule)", re.IGNORECASE),
    # 英文指令覆蓋
    re.compile(r"ignore.*(?:previous|all|above).*instruction", re.IGNORECASE),
    # 系統提示提取
    re.compile(r"系統提示|system\s*prompt", re.IGNORECASE),
    # 角色劫持
    re.compile(
        r"你(?:現在)?是(?:一個|一名)?(?:無限制|不受限|openai|gpt)", re.IGNORECASE
    ),
    # 直接 JSON 注入（嘗試跳過意圖理解）
    re.compile(r'```json\s*\n[^"]*"status"\s*:\s*"direct_response"', re.IGNORECASE),
    # 角色扮演
    re.compile(r"respond\s+as\s+if", re.IGNORECASE),
    re.compile(r"pretend\s+(?:you|to)", re.IGNORECASE),
]


def sanitize_user_input(text: str) -> str:
    """
    清洗用戶輸入，防止 prompt injection。

    將匹配到的注入模式替換為 [FILTERED]，並記錄被過濾的嘗試。

    Args:
        text: 原始用戶輸入

    Returns:
        清洗後的用戶輸入
    """
    if not text:
        return text

    sanitized = text
    filtered_count = 0

    for pattern in _INJECTION_PATTERNS:
        new_text, count = pattern.subn("[FILTERED]", sanitized)
        if count > 0:
            filtered_count += count
        sanitized = new_text

    if filtered_count > 0:
        logger.warning(
            "[PromptGuard] Filtered %d injection pattern(s) from user input: %s",
            filtered_count,
            text[:200],  # 只記錄前 200 字元避免日誌過大
        )

    return sanitized


# ---------------------------------------------------------------------------
# JSON Schema 驗證（意圖理解回應）
# ---------------------------------------------------------------------------

# 意圖理解預設安全回應
_INTENT_DEFAULT: Dict[str, Any] = {
    "status": "ready",
    "user_intent": "",
    "entities": {},
    "tasks": [],
    "aggregation_strategy": "combine_all",
}

# 意圖理解必要欄位及預設值
_INTENT_REQUIRED_FIELDS: Dict[str, Any] = {
    "status": "ready",
    "user_intent": "",
    "entities": {},
}

# 合法的 status 值
_VALID_INTENT_STATUSES = {"ready", "clarify", "direct_response"}


def validate_intent_response(
    data: Dict[str, Any], fallback_query: str
) -> Dict[str, Any]:
    """
    驗證意圖理解結果的 schema。

    確保必要欄位存在且值合法。不匹配時用預設值填充，不拋錯。

    Args:
        data: LLM 返回的解析後 JSON dict
        fallback_query: 當 user_intent 缺失時的 fallback

    Returns:
        驗證後的 dict（保證包含必要欄位）
    """
    if not isinstance(data, dict):
        logger.warning("[PromptGuard] Intent response is not a dict, using default")
        return {**_INTENT_DEFAULT, "user_intent": fallback_query}

    result = dict(data)

    # 驗證 status 欄位
    status = result.get("status")
    if status not in _VALID_INTENT_STATUSES:
        logger.warning(
            "[PromptGuard] Invalid intent status=%r, defaulting to 'ready'",
            status,
        )
        result["status"] = "ready"

    # 確保 user_intent 存在且非空
    user_intent = result.get("user_intent", "")
    if not user_intent:
        result["user_intent"] = fallback_query

    # 確保 entities 是 dict
    entities = result.get("entities")
    if not isinstance(entities, dict):
        result["entities"] = {}

    # 確保 tasks 是 list
    tasks = result.get("tasks")
    if not isinstance(tasks, list):
        result["tasks"] = []

    # status 為 clarify 時確保有 clarification_question
    if result["status"] == "clarify":
        if not result.get("clarification_question"):
            result["clarification_question"] = "請問您想查詢什麼？"

    # status 為 direct_response 時確保有 direct_response_text
    if result["status"] == "direct_response":
        if not result.get("direct_response_text"):
            result["direct_response_text"] = "你好！請問有什麼我可以幫忙的？"

    return result


# ---------------------------------------------------------------------------
# JSON Schema 驗證（反思回應）
# ---------------------------------------------------------------------------

_REFLECTION_DEFAULT: Dict[str, Any] = {
    "issues": [],
    "needs_retry": False,
    "cleaned_results": None,
}


def validate_reflection_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    驗證反思結果的 schema。

    Args:
        data: LLM 返回的解析後 JSON dict

    Returns:
        驗證後的 dict
    """
    if not isinstance(data, dict):
        logger.warning("[PromptGuard] Reflection response is not a dict, using default")
        return dict(_REFLECTION_DEFAULT)

    result = dict(data)

    # 確保 issues 是 list
    issues = result.get("issues")
    if not isinstance(issues, list):
        result["issues"] = []

    # 確保 needs_retry 是 bool
    needs_retry = result.get("needs_retry")
    if not isinstance(needs_retry, bool):
        result["needs_retry"] = False

    return result


# ---------------------------------------------------------------------------
# 統一入口：安全解析 + 驗證
# ---------------------------------------------------------------------------

_JSON_CODEBLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")


def parse_and_validate_json_response(
    response: str,
    context: str = "intent",
    fallback_query: str = "",
) -> Dict[str, Any]:
    """
    安全解析 JSON 回應並進行 schema 驗證。

    步驟：
    1. 嘗試從 markdown code block 提取 JSON
    2. 嘗試直接解析
    3. 根據 context 選擇對應的驗證函數
    4. 驗證失敗時回傳安全預設值（不拋錯）

    Args:
        response: LLM 原始回應文字
        context: 解析上下文，"intent" 或 "reflection"
        fallback_query: 意圖理解時 user_intent 缺失的 fallback

    Returns:
        解析並驗證後的 dict（保證不為 None）
    """
    if not response or not response.strip():
        logger.warning("[PromptGuard] Empty response, returning default")
        if context == "reflection":
            return dict(_REFLECTION_DEFAULT)
        return {**_INTENT_DEFAULT, "user_intent": fallback_query}

    # 嘗試從 markdown code block 提取
    extracted = response
    json_match = _JSON_CODEBLOCK_RE.search(response)
    if json_match:
        extracted = json_match.group(1)

    # 嘗試解析 JSON
    try:
        data = json.loads(extracted)
    except json.JSONDecodeError as e:
        logger.warning(
            "[PromptGuard] Failed to parse JSON in %s context: %s",
            context,
            e,
        )
        if context == "reflection":
            return dict(_REFLECTION_DEFAULT)
        return {**_INTENT_DEFAULT, "user_intent": fallback_query}

    # 根據 context 驗證 schema
    if context == "reflection":
        return validate_reflection_response(data)
    else:
        return validate_intent_response(data, fallback_query)
