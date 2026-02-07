"""
Governance System Validators
"""
from typing import Dict, Optional
import re


def validate_report_type(report_type: str) -> Dict:
    """
    驗證檢舉類型是否有效

    Args:
        report_type: 檢舉類型

    Returns:
        {"valid": bool, "error": str}
    """
    valid_types = ["spam", "harassment", "misinformation", "scam", "illegal", "other"]

    if not report_type:
        return {"valid": False, "error": "檢舉類型不能為空"}

    if report_type not in valid_types:
        return {"valid": False, "error": f"無效的檢舉類型: {report_type}"}

    return {"valid": True, "error": None}


def validate_content_type(content_type: str) -> Dict:
    """
    驗證內容類型是否有效

    Args:
        content_type: 內容類型 ('post' 或 'comment')

    Returns:
        {"valid": bool, "error": str}
    """
    valid_types = ["post", "comment"]

    if not content_type:
        return {"valid": False, "error": "內容類型不能為空"}

    if content_type not in valid_types:
        return {"valid": False, "error": f"無效的內容類型: {content_type}"}

    return {"valid": True, "error": None}


def validate_vote_type(vote_type: str) -> Dict:
    """
    驗證投票類型是否有效

    Args:
        vote_type: 投票類型 ('approve' 或 'reject')

    Returns:
        {"valid": bool, "error": str}
    """
    valid_types = ["approve", "reject"]

    if not vote_type:
        return {"valid": False, "error": "投票類型不能為空"}

    if vote_type not in valid_types:
        return {"valid": False, "error": f"無效的投票類型: {vote_type}"}

    return {"valid": True, "error": None}


def validate_violation_level(violation_level: Optional[str]) -> Dict:
    """
    驗證違規等級是否有效

    Args:
        violation_level: 違規等級 (可選)

    Returns:
        {"valid": bool, "error": str}
    """
    if not violation_level:
        return {"valid": True, "error": None}

    valid_levels = ["mild", "medium", "severe", "critical"]

    if violation_level not in valid_levels:
        return {"valid": False, "error": f"無效的違規等級: {violation_level}"}

    return {"valid": True, "error": None}


def validate_report_description(description: Optional[str]) -> Dict:
    """
    驗證檢舉描述

    Args:
        description: 檢舉描述（選填）

    Returns:
        {"valid": bool, "error": str}
    """
    if description is None:
        return {"valid": True, "error": None}

    # 檢查長度
    if len(description) > 1000:
        return {"valid": False, "error": "描述過長（最多 1000 字）"}

    # 檢查是否只包含空白
    if description.strip() == "":
        return {"valid": False, "error": "描述不能只包含空白"}

    return {"valid": True, "error": None}


def sanitize_description(description: str) -> str:
    """
    清理描述文本

    Args:
        description: 原始描述

    Returns:
        清理後的描述
    """
    if not description:
        return ""

    # 移除多餘空白
    description = ' '.join(description.split())

    # 移除前後空白
    description = description.strip()

    return description
