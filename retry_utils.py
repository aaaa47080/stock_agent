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


def with_timeout(timeout_seconds: float):
    """
    裝飾器：為函數添加超時限制

    Args:
        timeout_seconds: 超時時間（秒）

    注意：此裝飾器依賴於 signal 模組，在 Windows 上可能不可用
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"{func.__name__} 執行超時（{timeout_seconds}秒）")

            # 設置超時信號
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))

            try:
                result = func(*args, **kwargs)
            finally:
                # 恢復原始信號處理器
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result

        return wrapper
    return decorator


class CircuitBreaker:
    """
    斷路器模式實現
    當錯誤率超過閾值時，暫時停止調用，避免資源浪費
    """
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        """
        Args:
            failure_threshold: 失敗次數閾值
            timeout: 斷路器打開後的冷卻時間（秒）
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通過斷路器調用函數
        """
        # 檢查是否需要從 OPEN 切換到 HALF_OPEN
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "HALF_OPEN"
                print(f"  🔄 斷路器進入半開狀態，嘗試恢復...")
            else:
                raise Exception(f"斷路器已打開，請稍後再試（剩餘 {self.timeout - (time.time() - self.last_failure_time):.0f} 秒）")

        try:
            result = func(*args, **kwargs)

            # 成功調用，重置失敗計數
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
                print(f"  ✅ 斷路器已關閉，服務恢復正常")

            return result

        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
                print(f"  🔴 斷路器已打開（失敗次數: {self.failures}），暫停調用 {self.timeout} 秒")

            raise e
