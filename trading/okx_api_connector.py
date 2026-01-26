import requests
import json
import hmac
import hashlib
import base64
import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from dotenv import load_dotenv
from api.utils import logger

# Load environment variables with override to ensure .env file values take precedence
load_dotenv(override=True)

class OKXAPIConnector:
    """
    OKX API 連接器，支援現貨和期貨交易
    """
    _has_warned_missing_creds = False

    def __init__(self):
        # 嘗試從環境變數獲取 API 資訊
        self.api_key = os.getenv("OKX_API_KEY", "")
        self.secret_key = os.getenv("OKX_API_SECRET", "")  # <--- 已修正變數名稱
        self.passphrase = os.getenv("OKX_PASSPHRASE", "")

        if not all([self.api_key, self.secret_key, self.passphrase]):
            if not OKXAPIConnector._has_warned_missing_creds:
                logger.warning("[WARNING] 未找到 OKX API 憑證")
                logger.warning("請在 .env 文件中設置以下變數：")
                logger.warning("OKX_API_KEY=您的API密鑰")
                logger.warning("OKX_API_SECRET=您的API私鑰")
                logger.warning("OKX_PASSPHRASE=您的API密碼")
                OKXAPIConnector._has_warned_missing_creds = True

        # Use custom base URL if provided in .env, else use default
        self.base_url = os.getenv("OKX_BASE_URL", "https://www.okx.com")
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # 定義不需要簽名的公共端點
        self.public_endpoints = [
            "/public/instruments",
            "/market/ticker",
            "/market/tickers",
            "/market/candles",
            "/market/history-candles",
            "/public/funding-rate"
        ]

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
        # 檢查是否為公共端點
        is_public = any(endpoint.startswith(pub) for pub in self.public_endpoints)

        # 如果不是公共端點，且缺少憑證，則報錯
        if not is_public and not all([self.api_key, self.secret_key, self.passphrase]):
            return {"code": "50000", "msg": "❌ 未設置 OKX API Key。請在系統設定中輸入您的 OKX API 憑證。", "data": []}

        # 構建實際請求的 URL
        # 如果 base_url 已包含版本信息 (/api/v5)，則直接附加 endpoint；否則添加版本前綴
        if "/api/v5" in self.base_url:
            url = f"{self.base_url}{endpoint}"
        else:
            url = f"{self.base_url}/api/v5{endpoint}"

        # 準備請求參數
        headers = self.headers.copy()
        
        # 只有在有憑證且不是故意要忽略簽名的情況下才簽名
        # 但為了提高限頻，如果有的話即使是 public 我們通常也簽名
        # 但為了回應使用者需求：如果使用者想用 public 方式，這裡我們對於 public endpoint 可以選擇不簽名
        # 這裡策略：如果有 key 就簽名 (獲取更高限頻)，除非使用者指定要 public 模式 (這裡暫不實作複雜開關)
        # 或者：嚴格按照使用者建議，Public endpoint 就不簽名
        
        # 修正邏輯：如果 Keys 存在，為了 Rate Limit 還是建議簽名。
        # 但如果 Keys 不存在 且 是 Public Endpoint -> 允許通過。
        
        if all([self.api_key, self.secret_key, self.passphrase]):
             # 有 Key，執行簽名以獲得更高權限/限頻
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            
            # 構建請求路徑 (用於簽名)
            signature_endpoint = '/api/v5' + endpoint 

            if method.upper() == 'GET':
                query_string = '&'.join([f"{k}={v}" for k, v in (params or {}).items()]) if params else ""
                if query_string:
                    request_path = f"{signature_endpoint}?{query_string}"
                else:
                    request_path = signature_endpoint
                body = ""
            else:
                request_path = signature_endpoint
                body = json.dumps(data, separators=(',', ':')) if data else ""

            signature = self._generate_signature(timestamp, method, request_path, body)

            headers.update({
                "OK-ACCESS-KEY": self.api_key,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": self.passphrase
            })
            
            # 對於 POST/PUT 請求，確保 body 是 JSON 字符串
            if method.upper() not in ['GET', 'DELETE'] and not isinstance(data, str) and data:
                 data = body # 使用簽名時生成的 body 字符串
                 
        else:
            # 無 Key 且是 Public -> 不簽名，直接發送
            pass

        # 設置請求超時 (連接超時, 讀取超時)
        timeout = (10, 30)

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            elif method.upper() == 'POST':
                # 注意：如果上面有簽名，data 已經被轉成 json string (body)，如果是 requests.post(json=...) 會再次轉義
                # 所以這裡要小心。如果 headers 有 Content-Type: application/json，直接傳 data=body
                if isinstance(data, dict):
                     response = requests.post(url, headers=headers, json=data, timeout=timeout)
                else:
                     response = requests.post(url, headers=headers, data=data, timeout=timeout)
            elif method.upper() == 'PUT':
                if isinstance(data, dict):
                     response = requests.put(url, headers=headers, json=data, timeout=timeout)
                else:
                     response = requests.put(url, headers=headers, data=data, timeout=timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=timeout)
            else:
                return {"code": "000000", "msg": "不支援的 HTTP 方法", "data": []}

            # print(f"[DEBUG] API 回應: {response.status_code}")
            result = response.json()
            # print(f"[DEBUG] API 回應內容: {result}")
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

        # 添加止損止盈參數 (使用最新的 attachAlgoOrds 格式以修正錯誤 54070)
        attach_algo_ords = []
        algo_ord = {}

        if tpTriggerPx:
            algo_ord["tpTriggerPx"] = str(tpTriggerPx)
            algo_ord["tpOrdPx"] = str(tpOrdPx) if tpOrdPx else "-1"
            algo_ord["tpTriggerPxType"] = "last"
        
        if slTriggerPx:
            algo_ord["slTriggerPx"] = str(slTriggerPx)
            algo_ord["slOrdPx"] = str(slOrdPx) if slOrdPx else "-1"
            algo_ord["slTriggerPxType"] = "last"

        if algo_ord:
            attach_algo_ords.append(algo_ord)
            data["attachAlgoOrds"] = attach_algo_ords

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

    def get_tickers(self, instType: str) -> dict:
        """
        獲取所有產品行情資訊

        Args:
            instType: 產品類型 (SPOT, SWAP, FUTURES, OPTION)
        """
        endpoint = "/market/tickers"
        params = {"instType": instType}
        return self._make_request("GET", endpoint, params=params)

    def get_funding_rate(self, instId: str) -> dict:
        """
        獲取單個永續合約的當前資金費率

        Args:
            instId: 永續合約ID (如 BTC-USDT-SWAP)
        """
        endpoint = "/public/funding-rate"
        params = {"instId": instId}
        return self._make_request("GET", endpoint, params=params)

    def get_funding_rate_history(self, instId: str, limit: int = 100) -> dict:
        """
        獲取資金費率歷史數據

        Args:
            instId: 永續合約ID
            limit: 獲取數量 (Max 100)
        """
        endpoint = "/public/funding-rate-history"
        params = {"instId": instId, "limit": str(limit)}
        return self._make_request("GET", endpoint, params=params)

    def get_all_funding_rates(self) -> dict:
        """
        獲取所有 USDT 永續合約的資金費率，包含上下限資訊

        Returns:
            dict: 包含所有合約資金費率的字典，key 為幣種符號
        """
        # 先獲取所有 SWAP 產品以取得清單
        instruments = self.get_instruments("SWAP")
        if instruments.get("code") != "0":
            return {"error": "無法獲取合約列表"}

        funding_rates = {}

        # 篩選 USDT 本位永續合約
        usdt_swaps = [inst for inst in instruments.get("data", [])
                      if inst.get("instId", "").endswith("-USDT-SWAP")]

        # Helper function for parallel fetching with rate limiting
        import time
        def fetch_single_rate(inst_id):
            try:
                time.sleep(0.1)  # 100ms 間隔，避免觸發限流
                res = self.get_funding_rate(inst_id)
                if res.get("code") == "0" and res.get("data"):
                    return inst_id, res["data"][0]
            except Exception:
                pass
            return inst_id, None

        # 批量獲取資金費率 (並行處理)
        # 減少並發數到 3，避免 SSL 連接問題
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_inst = {executor.submit(fetch_single_rate, inst.get("instId")): inst for inst in usdt_swaps}
            
            for future in as_completed(future_to_inst):
                instId, data = future.result()
                if data:
                    try:
                        symbol = instId.replace("-SWAP", "")
                        
                        # 從回應中直接獲取上下限，若無則使用預設值
                        # OKX API 回傳的 maxFundingRate/minFundingRate 是小數 (例如 0.00375)，需轉為 %
                        max_rate = float(data.get("maxFundingRate", 0.0075)) * 100
                        min_rate = float(data.get("minFundingRate", -0.0075)) * 100
                        
                        # 處理下次資金費率 (可能是空字串)
                        next_rate_val = data.get("nextFundingRate")
                        next_rate = float(next_rate_val) * 100 if next_rate_val else None

                        funding_rates[symbol] = {
                            "instId": instId,
                            "fundingRate": float(data.get("fundingRate", 0)) * 100,
                            "nextFundingRate": next_rate,
                            "fundingTime": data.get("fundingTime"),
                            "nextFundingTime": data.get("nextFundingTime"),
                            "maxFundingRate": max_rate,
                            "minFundingRate": min_rate
                        }
                    except Exception as e:
                        print(f"[ERROR] Error processing funding rate for {instId}: {e}")

        return funding_rates

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
        # print(f"[DEBUG] 帳戶餘額API返回: {result}")
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