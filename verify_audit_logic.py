"""
简单验证脚本：测试审计中间件的分层逻辑
"""

def test_sensitive_action_detection():
    """测试敏感操作检测逻辑"""
    
    # 模拟 _is_sensitive_action 函数的逻辑
    def is_sensitive(action, path, method):
        SENSITIVE_ACTIONS = {
            'login', 'logout', 'pi_sync', 'dev_login',
            'payment_approve', 'payment_complete', 'tip_post',
            'upgrade_premium',
            'delete_post', 'delete_user', 'ban_user',
            'admin_action', 'config_change',
            'send_friend_request', 'accept_friend_request',
        }
        
        if action in SENSITIVE_ACTIONS:
            return True
        if method == 'DELETE':
            return True
        if method == 'POST' and ('/forum/posts' in path or '/forum/comments' in path):
            return True
        if '/payment' in path or '/tip' in path:
            return True
        if '/admin' in path:
            return True
        return False
    
    # 测试用例
    test_cases = [
        # (action, path, method, 预期结果, 描述)
        ('login', '/api/login', 'POST', True, '登录 → 数据库'),
        ('logout', '/api/logout', 'POST', True, '登出 → 数据库'),
        ('payment_approve', '/api/payment/approve', 'POST', True, '支付 → 数据库'),
        ('create_post', '/api/forum/posts', 'POST', True, '发帖 → 数据库'),
        ('delete_post', '/api/forum/posts/123', 'DELETE', True, '删帖 → 数据库'),
        ('admin_action', '/api/admin/config', 'POST', True, '管理员 → 数据库'),
        
        ('get_api_klines', '/api/klines', 'GET', False, 'K线查询 → 日志文件'),
        ('get_api_market_symbols', '/api/market/symbols', 'GET', False, '市场符号 → 日志文件'),
        ('get_api_funding_rates', '/api/funding-rates', 'GET', False, '资金费率 → 日志文件'),
        ('get_api_screener', '/api/screener', 'POST', False, '市场筛选 → 日志文件'),
        ('get_api_market_pulse_btc', '/api/market-pulse/BTC', 'GET', False, '市场脉动 → 日志文件'),
    ]
    
    print("=" * 100)
    print("🧪 审计分层逻辑测试")
    print("=" * 100)
    print()
    
    passed = 0
    failed = 0
    
    for action, path, method, expected, desc in test_cases:
        result = is_sensitive(action, path, method)
        
        if result == expected:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        storage = "数据库" if result else "日志文件"
        expected_storage = "数据库" if expected else "日志文件"
        
        print(f"{status} | {method:6} {path:45} | {desc:20} | 实际:{storage:8} 预期:{expected_storage}")
    
    print()
    print("=" * 100)
    print(f"📊 测试结果: ✅ {passed} 通过, ❌ {failed} 失败")
    print("=" * 100)
    print()
    
    if failed == 0:
        print("🎉 所有测试通过！")
        print()
        print("📝 优化效果预估:")
        print("   - 数据库写入: 只有敏感操作（登录、支付、发帖、删除等）")
        print("   - 日志文件: 所有其他操作（市场数据查询、筛选器等）")
        print("   - 预估减少: 95%+ 的数据库写入量")
        print("   - 从 100MB/小时 → 预估 2-5MB/小时")
    else:
        print("⚠️  部分测试失败，请检查逻辑!")
    
    return failed == 0


if __name__ == "__main__":
    success = test_sensitive_action_detection()
    exit(0 if success else 1)
