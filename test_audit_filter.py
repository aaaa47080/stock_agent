"""
审计过滤规则测试脚本

测试各种端点是否被正确过滤
"""
from api.middleware.audit import audit_middleware
from fastapi import Request
from unittest.mock import Mock, AsyncMock
import asyncio


class MockRequest:
    """模拟 FastAPI Request 对象"""
    def __init__(self, path, method="GET"):
        self.url = Mock()
        self.url.path = path
        self.method = method
        self.state = Mock()
        self.state.user = None
        self.client = Mock()
        self.client.host = "127.0.0.1"
        self.headers = {"user-agent": "test"}


async def test_audit_filter():
    """测试审计过滤规则"""
    
    # 记录是否调用了 AuditLogger.log
    logged_paths = []
    
    # Mock AuditLogger.log
    from core import audit
    original_log = audit.AuditLogger.log
    
    def mock_log(**kwargs):
        logged_paths.append(kwargs.get('endpoint', 'unknown'))
    
    audit.AuditLogger.log = mock_log
    
    # 模拟 call_next
    async def mock_call_next(request):
        response = Mock()
        response.status_code = 200
        response.headers = {}
        return response
    
    # 测试用例
    test_cases = [
        # (路径, 方法, 是否应该被记录)
        ("/health", "GET", False, "健康检查"),
        ("/ready", "GET", False, "就绪检查"),
        ("/validation-key.txt", "GET", False, "Pi验证"),
        ("/static/css/style.css", "GET", False, "静态CSS"),
        ("/js/main.js", "GET", False, "静态JS"),
        ("/images/logo.png", "GET", False, "静态图片"),
        ("/favicon.ico", "GET", False, "网站图标"),
        ("/ws/klines", "GET", False, "WebSocket"),
        ("/api/debug-log", "POST", False, "调试日志"),
        
        ("/api/klines", "GET", False, "K线数据查询"),
        ("/api/market/symbols", "GET", False, "市场符号"),
        ("/api/funding-rates", "GET", False, "资金费率"),
        ("/api/funding-rate/BTC", "GET", False, "单个资金费率"),
        ("/api/funding-rate-history/BTC", "GET", False, "费率历史"),
        ("/api/market-pulse/progress", "GET", False, "市场脉动进度"),
        
        ("/api/login", "POST", True, "登录"),
        ("/api/pi-sync", "POST", True, "Pi同步"),
        ("/api/forum/posts", "POST", True, "发帖"),
        ("/api/forum/posts/123", "DELETE", True, "删帖"),
        ("/api/payment/approve", "POST", True, "支付批准"),
        ("/api/premium/upgrade", "POST", True, "升级会员"),
        ("/api/friends/request", "POST", True, "好友请求"),
        ("/api/screener", "POST", True, "市场筛选"),
        ("/api/market-pulse/BTC", "GET", True, "市场脉动查询"),
    ]
    
    print("=" * 80)
    print("🧪 审计过滤规则测试")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for path, method, should_log, description in test_cases:
        logged_paths.clear()
        
        request = MockRequest(path, method)
        await audit_middleware(request, mock_call_next)
        
        was_logged = len(logged_paths) > 0
        
        # 检查结果
        if was_logged == should_log:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        expected = "应记录" if should_log else "应过滤"
        actual = "已记录" if was_logged else "已过滤"
        
        print(f"{status} | {method:6} {path:45} | {description:15} | {expected} -> {actual}")
    
    print()
    print("=" * 80)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 80)
    
    # 恢复原始函数
    audit.AuditLogger.log = original_log
    
    return failed == 0


async def main():
    success = await test_audit_filter()
    if success:
        print("\n🎉 所有测试通过！审计过滤规则工作正常。")
    else:
        print("\n⚠️  部分测试失败，请检查过滤规则。")


if __name__ == "__main__":
    asyncio.run(main())
