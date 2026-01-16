"""
重試機制工具
提供自動重試功能，用於處理 API 調用失敗的情況
"""
import time
from functools import wraps
from typing import Callable, Any

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    裝飾器：自動重試失敗的函數調用

    Args:
        max_retries: 最大重試次數
        delay: 初始延遲時間（秒）
        backoff: 延遲時間的倍增因子

    使用範例:
        @retry_on_failure(max_retries=3, delay=1.0)
        def call_api():
            # API 調用邏輯
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        print(f"  ⚠️  {func.__name__} 失敗 (嘗試 {attempt + 1}/{max_retries}): {e}")
                        print(f"  ⏳ {current_delay:.1f} 秒後重試...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"  ❌ {func.__name__} 達到最大重試次數，放棄重試")

            # 所有重試都失敗，拋出最後一個異常
            raise last_exception

        return wrapper
    return decorator
