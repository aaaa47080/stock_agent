"""
快速測試好友功能流程
測試帳號03加入04好友，04接受，然後傳訊息
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8111"

def test_friend_workflow():
    print("=" * 60)
    print("測試好友功能流程")
    print("=" * 60)
    
    # 使用新的測試帳號避免衝突
    user1 = {"id": "test-user-003", "token": "test-user-003"}
    user2 = {"id": "test-user-004", "token": "test-user-004"}
    
    # Step 1: User 003 發送好友請求給 User 004
    print(f"\n[1] {user1['id']} 發送好友請求給 {user2['id']}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/friends/request?user_id={user1['id']}",
            headers={"Authorization": f"Bearer {user1['token']}"},
            json={"target_user_id": user2['id']}
        )
        print(f"   狀態碼: {response.status_code}")
        print(f"   回應: {response.json()}")
        
        if response.status_code != 200:
            print(f"   ❌ 發送請求失敗")
            return False
        print("   ✅ 請求已發送")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    # Step 2: User 004 查看收到的好友請求
    print(f"\n[2] {user2['id']} 查看收到的好友請求...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/friends/requests/received?user_id={user2['id']}",
            headers={"Authorization": f"Bearer {user2['token']}"}
        )
        print(f"   狀態碼: {response.status_code}")
        data = response.json()
        print(f"   收到的請求數: {data.get('count', 0)}")
        
        if response.status_code != 200:
            print(f"   ❌ 查看請求失敗")
            return False
            
        if data.get('count', 0) == 0:
            print(f"   ❌ 沒有收到請求")
            return False
            
        print(f"   ✅ 找到請求: {data['requests'][0].get('username', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    # Step 3: User 004 接受好友請求
    print(f"\n[3] {user2['id']} 接受好友請求...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/friends/accept?user_id={user2['id']}",
            headers={"Authorization": f"Bearer {user2['token']}"},
            json={"target_user_id": user1['id']}
        )
        print(f"   狀態碼: {response.status_code}")
        print(f"   回應: {response.json()}")
        
        if response.status_code != 200:
            print(f"   ❌ 接受請求失敗")
            return False
        print("   ✅ 已成為好友")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    # Step 4: 驗證雙方的好友列表
    print("\n[4] 驗證好友列表...")
    for user in [user1, user2]:
        try:
            response = requests.get(
                f"{BASE_URL}/api/friends/list?user_id={user['id']}&limit=50&offset=0",
                headers={"Authorization": f"Bearer {user['token']}"}
            )
            data = response.json()
            print(f"   {user['id']}: {data.get('count', 0)} 位好友")
            
            if data.get('count', 0) == 0:
                print(f"   ❌ {user['id']} 好友列表為空")
                return False
        except Exception as e:
            print(f"   ❌ 錯誤: {e}")
            return False
    
    print("   ✅ 雙方好友列表都正確")
    
    # Step 5: User 003 發送訊息給 User 004
    print(f"\n[5] {user1['id']} 發送訊息給 {user2['id']}...")
    try:
        response = requests.post(
            f"{BASE_URL}/api/messages/send?user_id={user1['id']}",
            headers={"Authorization": f"Bearer {user1['token']}"},
            json={
                "recipient_user_id": user2['id'],
                "content": f"Hello from {user1['id']}! 測試訊息！",
                "message_type": "text"
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
    
    # Step 6: User 004 查看訊息
    print(f"\n[6] {user2['id']} 查看與 {user1['id']} 的對話...")
    try:
        response = requests.get(
            f"{BASE_URL}/api/messages/conversation/{user1['id']}?user_id={user2['id']}&limit=10&offset=0",
            headers={"Authorization": f"Bearer {user2['token']}"}
        )
        print(f"   狀態碼: {response.status_code}")
        data = response.json()
        print(f"   訊息數: {len(data.get('messages', []))}")
        
        if response.status_code != 200:
            print(f"   ❌ 查看訊息失敗")
            return False
            
        if len(data.get('messages', [])) == 0:
            print(f"   ❌ 沒有收到訊息")
            return False
            
        print(f"   最新訊息: {data['messages'][0].get('content', 'N/A')}")
        print("   ✅ 訊息接收成功")
    except Exception as e:
        print(f"   ❌ 錯誤: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有測試通過！好友功能正常運作！")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_friend_workflow()
    exit(0 if success else 1)
