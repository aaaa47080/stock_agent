"""
簡化測試：測試 001 和 002（已經是好友）的訊息功能
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8111"

def test_messaging():
    print("=" * 60)
    print("測試訊息功能（test-user-001 ↔ test-user-002）")
    print("=" * 60)
    
    user1 = {"id": "test-user-001", "token": "test-user-001"}
    user2 = {"id": "test-user-002", "token": "test-user-002"}
    
    # Step 1: 檢查好友關係
    print(f"\n[1] 檢查 {user1['id']} 和 {user2['id']} 的好友關係...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/friends/status/{user2['id']}?user_id={user1['id']}",
            headers={"Authorization": f"Bearer {user1['token']}"}
        )
        data = response.json()
        print(f"   狀態: {data.get('status')}")
        print(f"   是否為好友: {data.get('is_friend')}")
        
        if not data.get('is_friend'):
            print("   ❌ 不是好友，無法發送訊息")
            return False
        print("   ✅ 確認為好友")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    # Step 2: User 001 發送訊息給 User 002
    print(f"\n[2] {user1['id']} 發送訊息給 {user2['id']}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/messages/send?user_id={user1['id']}",
            headers={"Authorization": f"Bearer {user1['token']}"},
            json={
                "to_user_id": user2['id'],
                "content": f"測試訊息 @ {__import__('time').time()} - 來自 {user1['id']}"
            }
        )
        print(f"   狀態碼: {response.status_code}")
        print(f"   回應: {response.json()}")
        
        if response.status_code != 200:
            print(f"   ❌ 發送訊息失敗")
            return False
        print("   ✅ 訊息已發送")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    # Step 3: User 002 查看訊息
    print(f"\n[3] {user2['id']} 查看與 {user1['id']} 的對話...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/messages/with/{user1['id']}?user_id={user2['id']}&limit=5",
            headers={"Authorization": f"Bearer {user2['token']}"}
        )
        print(f"   狀態碼: {response.status_code}")
        data = response.json()
        
        if response.status_code != 200:
            print(f"   ❌ 查看訊息失敗")
            return False
        
        messages = data.get('messages', [])
        print(f"   訊息數: {len(messages)}")
        
        if len(messages) > 0:
            print(f"   最新訊息: {messages[0].get('content', 'N/A')}")
            print(f"   發送者: {messages[0].get('sender_user_id', 'N/A')}")
            print("   ✅ 訊息接收成功")
        else:
            print("   ⚠️ 沒有訊息")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    # Step 4: User 002 回覆訊息
    print(f"\n[4] {user2['id']} 回覆訊息給 {user1['id']}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/messages/send?user_id={user2['id']}",
            headers={"Authorization": f"Bearer {user2['token']}"},
            json={
                "to_user_id": user1['id'],
                "content": f"收到！這是來自 {user2['id']} 的回覆"
            }
        )
        print(f"   狀態碼: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ 回覆失敗")
            return False
        print("   ✅ 回覆已發送")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    # Step 5: User 001 查看對話
    print(f"\n[5] {user1['id']} 查看完整對話...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/messages/with/{user2['id']}?user_id={user1['id']}&limit=10",
            headers={"Authorization": f"Bearer {user1['token']}"}
        )
        data = response.json()
        messages = data.get('messages', [])
        
        print(f"   對話中共有 {len(messages)} 則訊息")
        for i, msg in enumerate(messages[:3]):  # 顯示最新3則
            sender = "我" if msg.get('from_user_id') == user1['id'] else "對方"
            print(f"   [{i+1}] {sender}: {msg.get('content', '')[:50]}...")
        
        print("   ✅ 對話查看成功")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有測試通過！訊息功能正常運作！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_messaging()
    exit(0 if success else 1)
