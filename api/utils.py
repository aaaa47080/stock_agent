import os
import json
import asyncio
import logging
from typing import Dict

logger = logging.getLogger("API")

# 定義一個哨兵物件來標記迭代結束
_STOP_ITERATION_SENTINEL = object()

def _safe_next(iterator):
    """
    安全地獲取下一個項目的輔助函數。
    如果遇到 StopIteration，則返回哨兵物件，而不是拋出異常。
    這避免了 StopIteration 異常在 run_in_executor 的 Future 中傳遞的問題。
    """
    try:
        return next(iterator)
    except StopIteration:
        return _STOP_ITERATION_SENTINEL

async def iterate_in_threadpool(generator):
    """
    將同步生成器包裝在執行緒池中運行，實現真正的異步串流。
    解決長時間分析任務阻塞主執行緒的問題。
    """
    loop = asyncio.get_running_loop()
    iterator = iter(generator)
    while True:
        try:
            # 在默認執行緒池中執行 _safe_next(iterator)
            # 使用 _safe_next 避免 StopIteration 傳遞給 Future
            item = await loop.run_in_executor(None, _safe_next, iterator)
            
            if item is _STOP_ITERATION_SENTINEL:
                break
                
            yield item
        except Exception as e:
            logger.error(f"串流生成錯誤: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            break

def update_env_file(keys: Dict[str, str], project_root: str):
    """Helper function to update or append keys to the .env file"""
    env_path = os.path.join(project_root, ".env")
    
    # Read existing lines
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = []

    # Prepare new content
    new_lines = []
    updated_keys = set()
    
    for line in lines:
        key_match = False
        for k, v in keys.items():
            if line.strip().startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                updated_keys.add(k)
                key_match = True
                break
        if not key_match:
            new_lines.append(line)
    
    # Append new keys that weren't in the file
    if len(new_lines) > 0 and not new_lines[-1].endswith('\n'):
        new_lines.append('\n')
        
    for k, v in keys.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")

    # Write back
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
