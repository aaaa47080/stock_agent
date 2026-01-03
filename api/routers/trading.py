import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request

from api.models import TradeExecutionRequest
from api.utils import logger
from trading.trade_executor import TradeExecutor
from utils.okx_auth import get_okx_connector_from_request, validate_okx_credentials
import api.globals as globals

router = APIRouter()

@router.post("/api/okx/test-connection")
async def test_okx_connection(request: Request):
    """
    測試 OKX API 連接 (BYOK Mode)

    用於前端驗證用戶輸入的金鑰是否有效
    不會存儲金鑰到後端
    """
    try:
        # 從請求頭中獲取憑證
        api_key = request.headers.get('X-OKX-API-KEY')
        secret_key = request.headers.get('X-OKX-SECRET-KEY')
        passphrase = request.headers.get('X-OKX-PASSPHRASE')

        if not all([api_key, secret_key, passphrase]):
            return {
                "success": False,
                "message": "缺少必要的憑證"
            }

        # 驗證憑證
        result = validate_okx_credentials(api_key, secret_key, passphrase)

        return {
            "success": result["valid"],
            "message": result["message"]
        }

    except Exception as e:
        logger.error(f"測試連接失敗: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"測試失敗: {str(e)}"
        }

@router.get("/api/account/assets")
async def get_account_assets(request: Request):
    """
    獲取帳戶資產餘額 (BYOK Mode)

    安全特性:
    - 從請求頭中讀取用戶的 OKX API 金鑰
    - 不在後端存儲金鑰
    - 無痕視窗無法訪問（因為 localStorage 不會保留）
    """
    # 從請求中獲取臨時 connector
    okx_connector = get_okx_connector_from_request(request)

    try:
        # 獲取帳戶餘額 (預設 USDT，也可以不傳參數獲取所有)
        # 這裡我們不傳 ccy 以獲取所有非零餘額
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: okx_connector.get_account_balance(ccy=None))
        
        if result.get("code") != "0":
             # 嘗試獲取更多錯誤細節
             msg = result.get("msg", "Unknown error")
             logger.error(f"獲取資產失敗: {msg}")
             raise HTTPException(status_code=500, detail=f"Exchange Error: {msg}")
             
        # 整理數據格式給前端
        data = result.get("data", [])
        if not data:
            return {"total_equity": 0, "details": []}
            
        account_data = data[0]
        total_equity = float(account_data.get("totalEq", 0))
        details = []
        
        for bal in account_data.get("details", []):
            if float(bal.get("eq", 0)) > 0: # 只顯示有餘額的幣種
                details.append({
                    "currency": bal.get("ccy"),
                    "balance": float(bal.get("eq")),
                    "available": float(bal.get("availBal")),
                    "frozen": float(bal.get("frozenBal")),
                    "usd_value": float(bal.get("eqUsd", 0))
                })
        
        # 按美元價值排序
        details.sort(key=lambda x: x["usd_value"], reverse=True)
        
        return {
            "total_equity": total_equity,
            "update_time": datetime.fromtimestamp(int(account_data.get("uTime", 0))/1000).isoformat(),
            "details": details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取帳戶資產失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/account/positions")
async def get_account_positions(request: Request):
    """
    獲取當前持倉 (包含現貨與合約) - BYOK Mode

    安全特性:
    - 從請求頭中讀取用戶的 OKX API 金鑰
    - 不在後端存儲金鑰
    """
    # 從請求中獲取臨時 connector
    okx_connector = get_okx_connector_from_request(request)

    try:
        loop = asyncio.get_running_loop()
        # 獲取所有持倉
        result = await loop.run_in_executor(None, lambda: okx_connector.get_positions("ANY"))
        
        if result.get("code") != "0":
             msg = result.get("msg", "Unknown error")
             raise HTTPException(status_code=500, detail=f"Exchange Error: {msg}")
             
        data = result.get("data", [])
        positions = []
        
        for pos in data:
            # 區分持倉類型
            inst_type = pos.get("instType")
            side = pos.get("posSide") # long, short, net
            
            # 處理基礎數據
            positions.append({
                "symbol": pos.get("instId"),
                "type": inst_type,
                "side": side,
                "size": float(pos.get("pos")), # 持倉數量
                "avg_price": float(pos.get("avgPx") or 0), # 開倉均價
                "mark_price": float(pos.get("markPx") or 0), # 標記價格
                "pnl": float(pos.get("upl") or 0), # 未實現盈虧
                "pnl_ratio": float(pos.get("uplRatio") or 0) * 100, # 盈虧率 %
                "leverage": float(pos.get("lever") or 1),
                "margin": float(pos.get("margin") or 0),
                "liq_price": float(pos.get("liqPx") or 0) # 強平價格
            })
            
        return {"positions": positions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取持倉失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/trade/execute")
async def execute_trade_api(trade_request: TradeExecutionRequest, request: Request):
    """
    手動確認後執行交易 (Human-in-the-loop) - BYOK Mode

    安全特性:
    - 從請求頭中讀取用戶的 OKX API 金鑰
    - 不在後端存儲金鑰
    """
    # 從請求中獲取臨時 connector
    okx_connector = get_okx_connector_from_request(request)

    try:
        # 使用臨時 connector 創建 executor
        executor = TradeExecutor(okx_connector=okx_connector)

        loop = asyncio.get_running_loop()

        if trade_request.market_type == "spot":
            result = await loop.run_in_executor(
                None,
                lambda: executor.execute_spot(
                    symbol=trade_request.symbol,
                    side=trade_request.side,
                    amount_usdt=trade_request.amount
                )
            )
        elif trade_request.market_type == "futures":
            result = await loop.run_in_executor(
                None,
                lambda: executor.execute_futures(
                    symbol=trade_request.symbol,
                    side=trade_request.side,
                    margin_amount=trade_request.amount,
                    leverage=trade_request.leverage,
                    stop_loss=trade_request.stop_loss,
                    take_profit=trade_request.take_profit
                )
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid market type")
            
        if result.get("status") == "failed":
            raise HTTPException(status_code=400, detail=result.get("error"))
            
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"交易執行失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
