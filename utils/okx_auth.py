"""
OKX API 認證工具 - BYOK (Bring Your Own Keys) 模式
從請求頭中提取用戶的 API 金鑰並創建臨時 connector
"""

from fastapi import HTTPException, Request
from trading.okx_api_connector import OKXAPIConnector
import os


def get_okx_connector_from_request(request: Request) -> OKXAPIConnector:
    """
    從請求頭中提取 OKX API 憑證，創建臨時 connector

    安全特性:
    1. 不存儲用戶金鑰到文件或數據庫
    2. 每次請求創建臨時 connector
    3. 請求結束後自動銷毀

    Args:
        request: FastAPI Request 對象

    Returns:
        OKXAPIConnector: 臨時的 API 連接器實例

    Raises:
        HTTPException: 如果缺少必要的憑證
    """
    # 從請求頭中提取憑證
    api_key = request.headers.get('X-OKX-API-KEY')
    secret_key = request.headers.get('X-OKX-SECRET-KEY')
    passphrase = request.headers.get('X-OKX-PASSPHRASE')

    if not all([api_key, secret_key, passphrase]):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_okx_credentials",
                "message": "請先設置 OKX API 金鑰。無痕視窗不會保存您的金鑰，請重新輸入。"
            }
        )

    # 創建臨時的 connector 實例，不使用環境變量
    connector = OKXAPIConnector()

    # 使用請求中的憑證覆蓋
    connector.api_key = api_key
    connector.secret_key = secret_key
    connector.passphrase = passphrase

    return connector


def get_legacy_okx_connector() -> OKXAPIConnector:
    """
    獲取傳統的全局 connector（向後兼容）

    注意: 這種方式不安全，僅用於向後兼容
    將在未來版本中移除

    Returns:
        OKXAPIConnector: 全局 connector 實例

    Raises:
        HTTPException: 如果全局 connector 未初始化
    """
    import api.globals as globals

    if not globals.okx_connector:
        raise HTTPException(
            status_code=503,
            detail="OKX 連接器尚未初始化"
        )

    return globals.okx_connector


def validate_okx_credentials(api_key: str, secret_key: str, passphrase: str) -> dict:
    """
    驗證 OKX API 憑證是否有效

    Args:
        api_key: API Key
        secret_key: Secret Key
        passphrase: Passphrase

    Returns:
        dict: {"valid": bool, "message": str, "details": dict}
    """
    try:
        # 創建臨時 connector
        connector = OKXAPIConnector()
        connector.api_key = api_key
        connector.secret_key = secret_key
        connector.passphrase = passphrase

        # 測試連接
        result = connector.get_account_balance("USDT")

        if result.get("code") == "0":
            return {
                "valid": True,
                "message": "OKX API 金鑰驗證成功",
                "details": {
                    "connection": "ok"
                }
            }
        else:
            error_msg = result.get("msg", "未知錯誤")
            return {
                "valid": False,
                "message": f"OKX API 驗證失敗: {error_msg}",
                "details": {
                    "error_code": result.get("code"),
                    "error_message": error_msg
                }
            }

    except Exception as e:
        return {
            "valid": False,
            "message": f"驗證過程發生錯誤: {str(e)}",
            "details": {
                "exception": str(e)
            }
        }
