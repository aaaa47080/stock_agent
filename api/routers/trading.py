import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException

from api.models import TradeExecutionRequest
from api.utils import logger
from trading.trade_executor import TradeExecutor
import api.globals as globals

router = APIRouter()

@router.get("/api/account/assets")
async def get_account_assets():
    """獲取帳戶資產餘額"""
    if not globals.okx_connector:
        raise HTTPException(status_code=503, detail="交易連接器尚未就緒")
    
    try:
        # 獲取帳戶餘額 (預設 USDT，也可以不傳參數獲取所有)
        # 這裡我們不傳 ccy 以獲取所有非零餘額
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: globals.okx_connector.get_account_balance(ccy=None))
        
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
async def get_account_positions():
    """獲取當前持倉 (包含現貨與合約)"""
    if not globals.okx_connector:
        raise HTTPException(status_code=503, detail="交易連接器尚未就緒")
        
    try:
        loop = asyncio.get_running_loop()
        # 獲取所有持倉
        result = await loop.run_in_executor(None, lambda: globals.okx_connector.get_positions("ANY"))
        
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
async def execute_trade_api(request: TradeExecutionRequest):
    """
    手動確認後執行交易 (Human-in-the-loop)
    """
    try:
        executor = TradeExecutor()
        
        loop = asyncio.get_running_loop()
        
        if request.market_type == "spot":
            result = await loop.run_in_executor(
                None, 
                lambda: executor.execute_spot(
                    symbol=request.symbol, 
                    side=request.side, 
                    amount_usdt=request.amount
                )
            )
        elif request.market_type == "futures":
            result = await loop.run_in_executor(
                None, 
                lambda: executor.execute_futures(
                    symbol=request.symbol, 
                    side=request.side, 
                    margin_amount=request.amount,
                    leverage=request.leverage,
                    stop_loss=request.stop_loss,
                    take_profit=request.take_profit
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
