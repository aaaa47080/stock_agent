"""
聊天系統 API 集成測試
需要先啟動 API 服務器: python api_server.py
"""
import requests
import time
import sys

BASE_URL = "http://localhost:8000"

# 測試配色
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

test_results = {
    'passed': 0,
    'failed': 0,
    'errors': []
}


def log_test(test_name, passed, error_msg=None):
    """記錄測試結果"""
    if passed:
        print(f"{GREEN}✓{RESET} {test_name}")
        test_results['passed'] += 1
    else:
        print(f"{RED}✗{RESET} {test_name}")
        test_results['failed'] += 1
        if error_msg:
            test_results['errors'].append(f"{test_name}: {error_msg}")


def check_server():
    """檢查服務器是否運行"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        return True
    except requests.exceptions.ConnectionError:
        return False


def test_get_conversations():
    """測試獲取對話列表"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/messages/conversations",
            params={"user_id": "test_user1"}
        )
        
        assert response.status_code == 200, f"狀態碼 {response.status_code}"
        data = response.json()
        assert 'conversations' in data, "回應缺少 conversations 欄位"
        assert 'total_unread' in data, "回應缺少 total_unread 欄位"
        log_test("GET /api/messages/conversations", True)
    except AssertionError as e:
        log_test("GET /api/messages/conversations", False, str(e))
    except Exception as e:
        log_test("GET /api/messages/conversations", False, str(e))


def test_get_conversation_messages():
    """測試獲取對話訊息"""
    # 先創建一個對話
    try:
        # 發送一條訊息以創建對話
        send_response = requests.post(
            f"{BASE_URL}/api/messages/send",
            params={"user_id": "test_user1"},
            json={"to_user_id": "test_user2", "content": "Test message for API"}
        )
        
        if send_response.status_code != 200:
            log_test("GET /api/messages/conversation/{id}", False, "無法創建測試對話")
            return
        
        conversation_id = send_response.json()['message']['conversation_id']
        
        # 獲取訊息
        response = requests.get(
            f"{BASE_URL}/api/messages/conversation/{conversation_id}",
            params={"user_id": "test_user2"}
        )
        
        assert response.status_code == 200, f"狀態碼 {response.status_code}"
        data = response.json()
        assert 'messages' in data, "回應缺少 messages 欄位"
        assert len(data['messages']) > 0, "訊息列表為空"
        log_test("GET /api/messages/conversation/{id}", True)
    except AssertionError as e:
        log_test("GET /api/messages/conversation/{id}", False, str(e))
    except Exception as e:
        log_test("GET /api/messages/conversation/{id}", False, str(e))


def test_send_message():
    """測試發送訊息"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/messages/send",
            params={"user_id": "test_user1"},
            json={"to_user_id": "test_user2", "content": "API test message"}
        )
        
        assert response.status_code == 200, f"狀態碼 {response.status_code}"
        data = response.json()
        assert data['success'] == True, "回應 success 為 False"
        assert 'message' in data, "回應缺少 message 欄位"
        assert data['message']['content'] == "API test message", "訊息內容不符"
        log_test("POST /api/messages/send", True)
    except AssertionError as e:
        log_test("POST /api/messages/send", False, str(e))
    except Exception as e:
        log_test("POST /api/messages/send", False, str(e))


def test_mark_as_read():
    """測試標記已讀"""
    # 先發送一條訊息
    try:
        send_response = requests.post(
            f"{BASE_URL}/api/messages/send",
            params={"user_id": "test_user1"},
            json={"to_user_id": "test_user2", "content": "Mark read test"}
        )
        
        if send_response.status_code != 200:
            log_test("POST /api/messages/read", False, "無法創建測試訊息")
            return
        
        conversation_id = send_response.json()['message']['conversation_id']
        
        # 標記已讀
        response = requests.post(
            f"{BASE_URL}/api/messages/read",
            params={"user_id": "test_user2"},
            json={"conversation_id": conversation_id}
        )
        
        assert response.status_code == 200, f"狀態碼 {response.status_code}"
        data = response.json()
        assert data['success'] == True, "回應 success 為 False"
        log_test("POST /api/messages/read", True)
    except AssertionError as e:
        log_test("POST /api/messages/read", False, str(e))
    except Exception as e:
        log_test("POST /api/messages/read", False, str(e))


def test_get_limits():
    """測試獲取限制狀態"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/messages/limits",
            params={"user_id": "test_user1"}
        )
        
        assert response.status_code == 200, f"狀態碼 {response.status_code}"
        data = response.json()
        assert 'is_pro' in data, "回應缺少 is_pro 欄位"
        assert 'message_limit' in data, "回應缺少 message_limit 欄位"
        assert 'greeting_limit' in data, "回應缺少 greeting_limit 欄位"
        log_test("GET /api/messages/limits", True)
    except AssertionError as e:
        log_test("GET /api/messages/limits", False, str(e))
    except Exception as e:
        log_test("GET /api/messages/limits", False, str(e))


def test_error_handling():
    """測試錯誤處理"""
    print(f"\n{YELLOW}=== 錯誤處理測試 ==={RESET}\n")
    
    # 測試1: 不存在的用戶
    try:
        response = requests.get(
            f"{BASE_URL}/api/messages/conversations",
            params={"user_id": "nonexistent_user"}
        )
        
        # 應該返回 401 或 403
        if response.status_code in [401, 403, 404]:
            log_test("拒絕不存在的用戶", True)
        else:
            log_test("拒絕不存在的用戶", False, f"狀態碼 {response.status_code}")
    except Exception as e:
        log_test("拒絕不存在的用戶", False, str(e))
    
    # 測試2: 缺少必要參數
    try:
        response = requests.post(
            f"{BASE_URL}/api/messages/send",
            params={"user_id": "test_user1"},
            json={"to_user_id": "test_user2"}  # 缺少 content
        )
        
        # 應該返回 422（驗證錯誤）
        if response.status_code == 422:
            log_test("參數驗證", True)
        else:
            log_test("參數驗證", False, f"狀態碼 {response.status_code}")
    except Exception as e:
        log_test("參數驗證", False, str(e))


def print_summary():
    """打印測試摘要"""
    print(f"\n{'='*60}")
    print(f"{YELLOW}測試摘要{RESET}")
    print(f"{'='*60}")
    print(f"通過: {GREEN}{test_results['passed']}{RESET}")
    print(f"失敗: {RED}{test_results['failed']}{RESET}")
    print(f"總計: {test_results['passed'] + test_results['failed']}")
    
    if test_results['failed'] > 0:
        print(f"\n{RED}失敗詳情:{RESET}")
        for error in test_results['errors']:
            print(f"  - {error}")
    
    print(f"{'='*60}\n")
    
    return 0 if test_results['failed'] == 0 else 1


def main():
    """主測試流程"""
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}聊天系統 API 集成測試{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}\n")
    
    # 檢查服務器
    print(f"{YELLOW}檢查 API 服務器...{RESET}")
    if not check_server():
        print(f"{RED}✗ API 服務器未運行{RESET}")
        print(f"{YELLOW}請先啟動服務器: python api_server.py{RESET}\n")
        sys.exit(1)
    print(f"{GREEN}✓{RESET} API 服務器運行中\n")
    
    # 執行測試
    print(f"{YELLOW}=== API 端點測試 ==={RESET}\n")
    test_get_conversations()
    test_get_conversation_messages()
    test_send_message()
    test_mark_as_read()
    test_get_limits()
    
    test_error_handling()
    
    # 輸出結果
    exit_code = print_summary()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
