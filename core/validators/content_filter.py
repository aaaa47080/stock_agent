"""
內容審核過濾器
"""
import re
from typing import Dict, List


def filter_sensitive_content(text: str) -> Dict:
    """
    檢查內容是否包含敏感資訊

    Args:
        text: 待檢查的文本

    Returns:
        {
            "valid": bool,
            "warnings": List[str]
        }
    """
    if not text:
        return {"valid": False, "warnings": ["內容不能為空"]}

    warnings = []

    # 檢查長度
    if len(text) < 20:
        warnings.append("描述過短（最少 20 字）")
    elif len(text) > 2000:
        warnings.append("描述過長（最多 2000 字）")

    # 檢查電子郵件
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    if re.search(email_pattern, text):
        warnings.append("包含電子郵件地址")

    # 檢查電話號碼（10 位以上連續數字）
    phone_pattern = r'\d{10,}'
    if re.search(phone_pattern, text):
        warnings.append("包含疑似電話號碼")

    # 檢查 URL（簡單版）
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    if urls:
        # 允許 Pi Network 官方域名
        allowed_domains = ['minepi.com', 'pi.network']
        for url in urls:
            if not any(domain in url for domain in allowed_domains):
                warnings.append("包含非官方網址")
                break

    # 敏感詞檢查（可從配置載入）
    sensitive_words = [
        '微信', 'wechat', 'telegram', 'whatsapp',
        '私聊', '加我', '聯繫我'
    ]

    text_lower = text.lower()
    for word in sensitive_words:
        if word in text_lower:
            warnings.append(f"包含敏感詞: {word}")
            break

    return {
        "valid": len(warnings) == 0,
        "warnings": warnings
    }


def sanitize_description(text: str) -> str:
    """
    清理描述文本（移除多餘空白、換行）

    Args:
        text: 原始文本

    Returns:
        清理後的文本
    """
    if not text:
        return ""

    # 移除多餘空白
    text = ' '.join(text.split())

    # 移除前後空白
    text = text.strip()

    return text
