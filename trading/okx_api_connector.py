import requests
import json
import hmac
import hashlib
import base64
import datetime
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

# Load environment variables with override to ensure .env file values take precedence
load_dotenv(override=True)

class OKXAPIConnector:
    """
    OKX API 連接器，支援現貨和期貨交易
    """
    def __init__(self):
        # 嘗試從環境變數獲取 API 資訊
        self.api_key = os.getenv("OKX_API_KEY", "")
        self.secret_key = os.getenv("OKX_API_SECRET", "")  # <--- 已修正變數名稱
        self.passphrase = os.getenv("OKX_PASSPHRASE", "")

        if not all([self.api_key, self.secret_key, self.passphrase]):
            print("[WARNING] 未找到 OKX API 憑證")
            print("請在 .env 文件中設置以下變數：")
            print("OKX_API_KEY=您的API密鑰")
            print("OKX_API_SECRET=您的API私鑰")
            print("OKX_PASSPHRASE=您的API密碼")

        # Use custom base URL if provided in .env, else use default
        self.base_url = os.getenv("OKX_BASE_URL", "https://www.okx.com")
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """
        生成 OKX API 簽名
        """
        if not all([self.secret_key, self.passphrase]):
            return ""

        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256,
        )
        signature = base64.b64encode(mac.digest()).decode()
        return signature

    def _make_request(self, method: str, endpoint: str, params: dict = None, data: dict = None) -> dict:
        """
        發送 API 請求
        """
        if not all([self.api_key, self.secret_key, self.passphrase]):
            return {"code": "000000", "msg": "API 憑證未設置", "data": []}

        # 構建實際請求的 URL
        # 如果 base_url 已包含版本信息 (/api/v5)，則直接附加 endpoint；否則添加版本前綴
        if "/api/v5" in self.base_url:
            url = f"{self.base_url}{endpoint}"
        else:
            url = f"{self.base_url}/api/v5{endpoint}"

        # 準備請求參數
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        headers = self.headers.copy()

        # 構建請求路徑 (用於簽名)
        # 根據 OKX API V5 文檔，requestPath 應包含完整的 API V5 路徑，包括查詢參數
        # 簽名中的路徑必須始終以 /api/v5 開頭
        signature_endpoint = '/api/v5' + endpoint  # 簽名時始終使用 /api/v5 前綴

        if method.upper() == 'GET':
            query_string = '&'.join([f"{k}={v}" for k, v in (params or {}).items()]) if params else ""
            if query_string:
                request_path = f"{signature_endpoint}?{query_string}"  # 例如: '/api/v5/account/balance?ccy=USDT'
            else:
                request_path = signature_endpoint  # 例如: '/api/v5/account/balance'
            body = ""
        else:
            request_path = signature_endpoint  # 例如: '/api/v5/account/balance'
            body = json.dumps(data, separators=(',', ':')) if data else ""

        # Debug: Show the exact message being signed
        message_to_sign = timestamp + method.upper() + request_path + body
        print(f"[DEBUG] 消息內容 (簽名): {message_to_sign}")

        signature = self._generate_signature(timestamp, method, request_path, body)
        print(f"[DEBUG] 簽名結果: {signature}")

        headers.update({
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase
        })

        # Debug: Print headers to check
        print(f"[DEBUG] API 請求: {method} {endpoint}")
        print(f"[DEBUG] 請求路徑 (用於簽名): {request_path}")
        print(f"[DEBUG] 請求體: {body}")
        print(f"[DEBUG] Headers: {dict(headers)}")

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, data=body)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, data=body)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)
            else:
                return {"code": "000000", "msg": "不支援的 HTTP 方法", "data": []}

            print(f"[DEBUG] API 回應: {response.status_code}")
            result = response.json()
            print(f"[DEBUG] API 回應內容: {result}")
            return result

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] 請求異常: {str(e)}")
            return {"code": "000000", "msg": f"請求錯誤: {str(e)}", "data": []}
        except Exception as e:
            print(f"[ERROR] 其他異常: {str(e)}")
            return {"code": "000000", "msg": f"未知錯誤: {str(e)}", "data": []}

    # --- 帳戶資訊相關 ---

    def get_account_balance(self, ccy: str = "USDT") -> dict:
        """
        獲取帳戶餘額

        Args:
            ccy: 幣別 (預設 USDT)
        """
        endpoint = "/account/balance"
        params = {"ccy": ccy} if ccy else {}
        return self._make_request("GET", endpoint, params=params)

    def get_positions(self, instType: str = "ANY") -> dict:
        """
        獲取持倉資訊

        Args:
            instType: 產品類型 (SPOT, MARGIN, SWAP, FUTURES, OPTION, ANY)
        """
        endpoint = "/account/positions"
        params = {"instType": instType} if instType != "ANY" else {}
        return self._make_request("GET", endpoint, params=params)

    def get_account_config(self) -> dict:
        """
        獲取帳戶配置資訊
        """
        endpoint = "/account/config"
        return self._make_request("GET", endpoint)

    # --- 現貨交易相關 ---

    def place_spot_order(self, instId: str, side: str, ordType: str, sz: str, px: str = None) -> dict:
        """
        下現貨訂單

        Args:
            instId: 產品ID (如 BTC-USDT)
            side: 買賣方向 (buy, sell)
            ordType: 訂單類型 (market, limit, etc.)
            sz: 數量
            px: 價格 (限價單時需要)
        """
        endpoint = "/trade/order"
        data = {
            "instId": instId,
            "tdMode": "cash",  # 現貨交易模式
            "side": side,
            "ordType": ordType,
            "sz": str(sz)
        }

        if ordType == "limit" and px:
            data["px"] = str(px)

        return self._make_request("POST", endpoint, data=data)

    def get_spot_orders(self, instId: str, state: str = "live") -> dict:
        """
        獲取現貨訂單狀態

        Args:
            instId: 產品ID
            state: 訂單狀態 (live, filled, cancelled, etc.)
        """
        endpoint = "/trade/orders-pending"
        params = {"instId": instId, "state": state}
        return self._make_request("GET", endpoint, params=params)

    # --- 期貨交易相關 ---

    def place_futures_order(self, instId: str, side: str, ordType: str, sz: str,
                           posSide: str, px: str = None, lever: str = "5",
                           slTriggerPx: str = None, slOrdPx: str = None,
                           tpTriggerPx: str = None, tpOrdPx: str = None) -> dict:
        """
        下期貨訂單

        Args:
            instId: 產品ID (如 BTC-USDT-SWAP)
            side: 買賣方向 (buy, sell)
            ordType: 訂單類型
            sz: 數量
            posSide: 倉位方向 (long, short, net)
            px: 價格
            lever: 槓桿倍數
            slTriggerPx: 止損触发价
            slOrdPx: 止损委托价 (市价单设为-1)
            tpTriggerPx: 止盈触发价
            tpOrdPx: 止盈委托价 (市价单设为-1)
        """
        endpoint = "/trade/order"
        data = {
            "instId": instId,
            "tdMode": "cross",  # 交叉槓桿模式
            "side": side,
            "ordType": ordType,
            "sz": str(sz),
            "posSide": posSide,
            "lever": str(lever)
        }

        if ordType == "limit" and px:
            data["px"] = str(px)

        # 添加止损止盈参数
        if slTriggerPx:
            data["slTriggerPx"] = str(slTriggerPx)
            data["slOrdPx"] = str(slOrdPx) if slOrdPx else "-1"  # -1 表示市价止损

        if tpTriggerPx:
            data["tpTriggerPx"] = str(tpTriggerPx)
            data["tpOrdPx"] = str(tpOrdPx) if tpOrdPx else "-1"  # -1 表示市价止盈

        return self._make_request("POST", endpoint, data=data)

    def get_futures_positions(self, instId: str = None) -> dict:
        """
        獲取期貨持倉

        Args:
            instId: 產品ID (可選)
        """
        endpoint = "/account/positions"
        params = {"instType": "SWAP"}
        if instId:
            params["instId"] = instId
        return self._make_request("GET", endpoint, params=params)

    def set_leverage(self, instId: str, lever: str, mgnMode: str = "cross", posSide: str = None) -> dict:
        """
        設置槓桿倍數

        Args:
            instId: 產品ID
            lever: 槓桿倍數
            mgnMode: 保證金模式 (cross, isolated)
            posSide: 持倉方向 (long, short, net) - 在單向持倉模式下使用 'net'
        """
        endpoint = "/account/set-leverage"
        data = {
            "instId": instId,
            "lever": str(lever),
            "mgnMode": mgnMode
        }

        # Only add posSide if provided (required in some position modes)
        if posSide:
            data["posSide"] = posSide

        return self._make_request("POST", endpoint, data=data)

    # --- 市場資料相關 ---

    def get_instruments(self, instType: str, instId: str = None) -> dict:
        """
        獲取交易產品的基礎信息（包含lot size等規則）

        Args:
            instType: 產品類型 (SPOT, SWAP, FUTURES, OPTION)
            instId: 產品ID (可選)
        """
        endpoint = "/public/instruments"
        params = {"instType": instType}
        if instId:
            params["instId"] = instId
        return self._make_request("GET", endpoint, params=params)

    def get_ticker(self, instId: str) -> dict:
        """
        獲取產品行情資訊

        Args:
            instId: 產品ID
        """
        endpoint = "/market/ticker"
        params = {"instId": instId}
        return self._make_request("GET", endpoint, params=params)

    def get_account_and_position_risk(self) -> dict:
        """
        獲取帳戶和持倉風險資訊
        """
        endpoint = "/account/account-position-risk"
        return self._make_request("GET", endpoint)

    # --- 測試連接 ---

    def test_connection(self) -> bool:
        """
        測試 API 連接
        """
        # 先測試比較基本的帳戶餘額接口
        result = self.get_account_balance("USDT")
        print(f"[DEBUG] 帳戶餘額API返回: {result}")
        return result.get("code") == "0"

def test_okx_api():
    """
    測試 OKX API 功能
    """
    print("[TEST] 開始測試 OKX API 連接...")
    api = OKXAPIConnector()

    # 檢查 API 憑證
    if not all([api.api_key, api.secret_key, api.passphrase]):
        print("[ERROR] 未設置 API 憑證，無法進行測試")
        print("   請在 .env 文件中設置 OKX API 憑證")
        return

    # 測試連接
    if api.test_connection():
        print("[SUCCESS] API 連接成功！")
    else:
        print("[ERROR] API 連接失敗")
        return

    print("\n" + "="*50)
    print("[ACCOUNT] 帳戶資訊測試")
    print("="*50)

    # 獲取帳戶餘額
    print("\n[INFO] 獲取帳戶餘額...")
    balance = api.get_account_balance("USDT")
    print(f"帳戶餘額結果: {balance}")

    # 獲取帳戶配置
    print("\n[INFO] 獲取帳戶配置...")
    config = api.get_account_config()
    print(f"帳戶配置結果: {config}")

    # 獲取持倉資訊
    print("\n[INFO] 獲取所有持倉...")
    positions = api.get_positions("ANY")
    print(f"持倉資訊結果: {positions}")

    print("\n" + "="*50)
    print("[TRADING] 交易功能測試")
    print("="*50)

    # 獲取市場行情（不需要認證）
    print("\n[INFO] 獲取市場行情 (BTC-USDT)...")
    ticker = api.get_ticker("BTC-USDT")  # 使用 BTC-USDT 作為示範
    print(f"市場行情結果: {ticker}")

    # 獲取期貨持倉
    print("\n[INFO] 獲取期貨持倉...")
    futures_positions = api.get_futures_positions()
    print(f"期貨持倉結果: {futures_positions}")

    print("\n" + "="*50)
    print("[SUCCESS] 測試完成！")
    print("[READY] OKX API 連接器已準備就緒")
    print("   您可以使用此連接器來執行自動交易")
    print("="*50)

if __name__ == "__main__":
    test_okx_api()