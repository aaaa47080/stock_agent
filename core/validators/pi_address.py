"""
Pi Network 地址驗證器
"""
import re
from typing import Tuple


def validate_pi_address(address: str) -> Tuple[bool, str]:
    """
    驗證 Pi Network 地址格式

    Pi 地址特徵：
    - 以 'G' 開頭
    - 長度 56 字符
    - 僅包含大寫字母和數字（Base32: A-Z, 2-7）

    Args:
        address: 錢包地址

    Returns:
        (is_valid, error_message)
    """
    if not address or not isinstance(address, str):
        return False, "地址不能為空"

    # 移除空白
    address = address.strip()

    # 檢查長度
    if len(address) != 56:
        return False, f"地址長度必須為 56 字符（當前: {len(address)}）"

    # 檢查開頭
    if not address.startswith('G'):
        return False, "Pi Network 地址必須以 'G' 開頭"

    # 檢查字符集（Base32: A-Z, 2-7，注意不包含 '1'）
    pattern = r'^G[A-Z234567]{55}$'
    if not re.match(pattern, address):
        return False, "地址包含無效字符（僅允許 A-Z 和 2-7）"

    return True, ""


def validate_pi_tx_hash(tx_hash: str) -> Tuple[bool, str]:
    """
    驗證 Pi 交易哈希格式（64 字符十六進制）

    Args:
        tx_hash: 交易哈希

    Returns:
        (is_valid, error_message)
    """
    if not tx_hash:
        return True, ""  # 交易哈希是可選的

    tx_hash = tx_hash.strip()

    if len(tx_hash) != 64:
        return False, f"交易哈希必須為 64 字符（當前: {len(tx_hash)}）"

    pattern = r'^[a-fA-F0-9]{64}$'
    if not re.match(pattern, tx_hash):
        return False, "交易哈希必須為十六進制字符"

    return True, ""


def mask_wallet_address(address: str, mask_length: int = 4) -> str:
    """
    遮罩錢包地址以保護隱私

    例如：GABCDEF123456...XYZ789 (前後各保留 mask_length 字符)

    Args:
        address: 完整地址
        mask_length: 前後保留字符數

    Returns:
        遮罩後的地址
    """
    if not address or len(address) <= mask_length * 2:
        return address

    prefix = address[:mask_length]
    suffix = address[-mask_length:]
    return f"{prefix}...{suffix}"
