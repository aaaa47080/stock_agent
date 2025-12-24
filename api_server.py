import os
import sys
import json
import asyncio
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import uvicorn
from dotenv import load_dotenv

# 將專案根目錄加入 Python 路徑
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from interfaces.chat_interface import CryptoAnalysisBot
from analysis.crypto_screener import screen_top_cryptos
from core.config import SUPPORTED_EXCHANGES, DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT
from core.database import add_to_watchlist, remove_from_watchlist, get_watchlist
from data.market_data import get_klines

load_dotenv()

app = FastAPI(title="Crypto Trading System API")
bot = CryptoAnalysisBot()

# 定義請求模型
class QueryRequest(BaseModel):
    message: str
    interval: str = DEFAULT_INTERVAL
    limit: int = DEFAULT_KLINES_LIMIT
    manual_selection: Optional[List[str]] = None

class ScreenerRequest(BaseModel):
    exchange: str = SUPPORTED_EXCHANGES[0]

class WatchlistRequest(BaseModel):
    user_id: str
    symbol: str

class KlineRequest(BaseModel):
    symbol: str
    exchange: str = SUPPORTED_EXCHANGES[0]
    interval: str = "1d"
    limit: int = 100

# --- [正式版支付註解區塊] ---
# 當你要正式上線並收款時，請取消以下代碼的註解，並在 .env 設定 PI_API_KEY
# PI_API_KEY = os.getenv("PI_API_KEY", "你的_PI_API_KEY")
# PI_PLATFORM_API_URL = "https://api.minepi.com/v2"
# 
# class PaymentDTO(BaseModel):
#     paymentId: str
#     txid: Optional[str] = None
#
# @app.post("/api/payment/approve")
# async def approve_payment(data: PaymentDTO):
#     import requests
#     # 告訴 Pi 伺服器你準備好接受這筆訂單了
#     headers = {"Authorization": f"Key {PI_API_KEY}"}
#     resp = requests.post(f"{PI_PLATFORM_API_URL}/payments/{data.paymentId}/approve", headers=headers, json={})
#     return resp.json() if resp.status_code == 200 else {"error": "failed"}
#
# @app.post("/api/payment/complete")
# async def complete_payment(data: PaymentDTO):
#     import requests
#     # 當用戶簽名成功後，最後確認交易
#     headers = {"Authorization": f"Key {PI_API_KEY}"}
#     resp = requests.post(f"{PI_PLATFORM_API_URL}/payments/{data.paymentId}/complete", headers=headers, json={"txid": data.txid})
#     # 在這裡發放你的虛擬商品 (例如：開通 VIP 分析權限)
#     return resp.json() if resp.status_code == 200 else {"error": "failed"}

# --- API 端點 ---

@app.post("/api/analyze")
async def analyze_crypto(request: QueryRequest):
    """
    處理分析請求，並以串流 (Streaming) 方式回傳結果
    """
    async def event_generator():
        try:
            # 使用 bot 的 process_message 生成器
            # 注意：process_message 是一個同步生成器，我們用 loop.run_in_executor 跑在後台
            # 或者直接疊代它 (因為它內部有 I/O 操作)
            for part in bot.process_message(request.message, request.interval, request.limit, request.manual_selection):
                # 包裝成 JSON 格式發送給前端
                yield f"data: {json.dumps({'content': part})}\n\n"
                await asyncio.sleep(0.01) # 微小延遲確保串流順暢
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/config")
async def get_config():
    """回傳前端需要的配置資訊"""
    return {
        "supported_exchanges": SUPPORTED_EXCHANGES,
        "default_interval": DEFAULT_INTERVAL,
        "default_limit": DEFAULT_KLINES_LIMIT
    }

@app.post("/api/screener")
async def run_screener(request: ScreenerRequest):
    """回傳市場篩選數據"""
    try:
        summary_df, top_performers, oversold, overbought = screen_top_cryptos(
            exchange=request.exchange,
            limit=20,
            interval="1d"
        )

        return {
            "top_performers": top_performers.to_dict(orient="records"),
            "oversold": oversold.to_dict(orient="records"),
            "overbought": overbought.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 自選清單 API ---

@app.get("/api/watchlist/{user_id}")
async def get_user_watchlist(user_id: str):
    """獲取用戶的自選清單"""
    try:
        symbols = get_watchlist(user_id)
        return {"symbols": symbols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist/add")
async def add_watchlist(request: WatchlistRequest):
    """新增幣種到自選清單"""
    try:
        add_to_watchlist(request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已加入自選清單"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/watchlist/remove")
async def remove_watchlist(request: WatchlistRequest):
    """從自選清單移除幣種"""
    try:
        remove_from_watchlist(request.user_id, request.symbol.upper())
        return {"success": True, "message": f"{request.symbol} 已從自選清單移除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- K 線數據 API (給圖表使用) ---

@app.post("/api/klines")
async def get_klines_data(request: KlineRequest):
    """獲取 K 線數據供圖表顯示"""
    try:
        df = get_klines(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            limit=request.limit
        )

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"找不到 {request.symbol} 的數據")

        # 轉換為 TradingView Lightweight Charts 格式
        klines = []
        for _, row in df.iterrows():
            klines.append({
                "time": int(row['timestamp'].timestamp()) if hasattr(row['timestamp'], 'timestamp') else int(row['timestamp'] / 1000),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close'])
            })

        return {
            "symbol": request.symbol,
            "interval": request.interval,
            "klines": klines
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 靜態檔案與頁面 ---

# 掛載 web 資料夾，提供前端靜態檔案
app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/")
async def read_index():
    """返回主頁面 index.html"""
    return FileResponse("web/index.html")

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 Pi Crypto Insight API Server 啟動中...")
    print(f"🏠 本地網址: http://localhost:8000")
    print("📱 請在 Pi Browser 中使用 HTTPS 網址訪問 (如透過 ngrok)")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8111)
