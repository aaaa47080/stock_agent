import os
import sys
import asyncio
import time
import signal
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services import refresh_all_market_pulse_data, load_market_pulse_cache
from api.globals import ANALYSIS_STATUS
from core.config import MARKET_PULSE_UPDATE_INTERVAL

# 控制旗標
running = True

def handle_exit(signum, frame):
    global running
    print("\n\n🛑 接獲停止信號，正在優雅關閉 Worker...")
    running = False

signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

async def progress_monitor(task):
    """監控並顯示進度條"""
    start_time = time.time()
    
    # ANSI Colors
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    
    while not task.done() and running:
        total = ANALYSIS_STATUS.get("total", 0)
        completed = ANALYSIS_STATUS.get("completed", 0)
        
        if total > 0:
            pct = (completed / total) * 100
            elapsed = time.time() - start_time
            
            # 進度條
            bar_len = 40
            filled = int(bar_len * completed // total)
            bar = '█' * filled + '░' * (bar_len - filled)
            
            # 估計剩餘時間
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            
            status_line = (
                f"\r{CYAN}⚡ [分析進度]{RESET} |{bar}| "
                f"{YELLOW}{completed}/{total}{RESET} ({pct:5.1f}%)"
                f"[{elapsed:.0f}s / ETA: {eta:.0f}s]"
            )
            sys.stdout.write(status_line)
            sys.stdout.flush()
        else:
            sys.stdout.write(f"\r{CYAN}⚡ [準備中]{RESET} 正在獲取市場清單...")
            sys.stdout.flush()
            
        await asyncio.sleep(0.2)
    
    print() # New line after done

async def run_worker():
    """Worker 主迴圈"""
    print("=" * 60)
    print("   🤖 MARKET PULSE WORKER - 獨立數據分析進程")
    print("=" * 60)
    
    # ⭐ 啟動時先從硬碟載入現有的分析結果
    print("📦 正在載入現有分析快取...")
    load_market_pulse_cache()
    
    while running:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 開始全市場掃描...")
        
        # 創建分析任務
        task = asyncio.create_task(refresh_all_market_pulse_data())
        
        try:
            timestamp = await task
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 掃描完成！數據已更新。")
            print(f"   - 下次更新時間: {MARKET_PULSE_UPDATE_INTERVAL/3600:.1f} 小時後")
        except Exception as e:
            print(f"\n❌ 掃描發生錯誤: {e}")
        
        # 等待下一次更新 (可被中斷)
        wait_steps = 100
        step_time = MARKET_PULSE_UPDATE_INTERVAL / wait_steps
        
        for _ in range(wait_steps):
            if not running: break
            await asyncio.sleep(step_time)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass