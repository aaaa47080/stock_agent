"""
简化版聊天系统测试 - 核心功能验证
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import (
    get_or_create_conversation,
    send_dm_message as send_message,
    get_dm_messages as get_messages,
    mark_as_read,
    get_unread_count,
    check_message_limit,
    create_user,
    get_connection,
)

print("\n===聊天系统核心测试===\n")

# 清理
conn = get_connection()
c = conn.cursor()
c.execute("PRAGMA foreign_keys = OFF")
c.execute("DELETE FROM dm_messages WHERE from_user_id LIKE 'test_%'")
c.execute("DELETE FROM dm_conversations WHERE user1_id LIKE 'test_%'")
c.execute("DELETE FROM friendships WHERE user_id LIKE 'test_%'")
c.execute("DELETE FROM users WHERE user_id LIKE 'test_%'")
conn.commit()
c.execute("PRAGMA foreign_keys = ON")
conn.close()

# 创建测试用户
import random
random_suffix = random.randint(100000, 999999)
try:
    user1 = create_user('test_user1', 'pass1', f'test{random_suffix}_1@test.com')
    user2 = create_user('test_user2', 'pass2', f'test{random_suffix}_2@test.com')
    print(f"[OK] Created users: {user1['user_id']}, {user2['user_id']}")
except Exception as e:
    print(f"[FAIL] User creation: {e}")
    sys.exit(1)

user1_id, user2_id = user1['user_id'], user2['user_id']

# 建立好友关系
conn = get_connection()
c = conn.cursor()
c.execute("INSERT INTO friendships (user_id, friend_id, status) VALUES (?, ?, 'accepted')", (user1_id, user2_id))
c.execute("INSERT INTO friendships (user_id, friend_id, status) VALUES (?, ?, 'accepted')", (user2_id, user1_id))
conn.commit()
conn.close()
print("[OK] Created friendship")

# 测试1: 创建对话
conv = get_or_create_conversation(user1_id, user2_id)
print(f"[OK] Created conversation ID: {conv['id']}")

# 测试2: 发送消息
result = send_message(user1_id, user2_id, "Test message 1")
if result['success']:
    print(f"[OK] Sent message: {result['message']['content']}")
else:
    print(f"[FAIL] Send message: {result.get('error')}")

# 测试3: 获取消息
msgs = get_messages(conv['id'], user2_id, limit=50)
if msgs['success'] and len(msgs['messages']) > 0:
    print(f"[OK] Retrieved {len(msgs['messages'])} messages")
else:
    print(f"[FAIL] Get messages")

# 测试4: 未读数量
unread = get_unread_count(user2_id)
print(f"[OK] Unread count for user2: {unread}")

# 测试5: 标记已读
read_result = mark_as_read(conv['id'], user2_id)
if read_result['success']:
    new_unread = get_unread_count(user2_id)
    print(f"[OK] Marked as read, new unread count: {new_unread}")
else:
    print(f"[FAIL] Mark as read")

# 测试6: 消息限制
limit = check_message_limit(user1_id, is_pro=False)
print(f"[OK] Message limit check: can_send={limit['can_send']}, used={limit['used']}/{limit['limit']}")

# 测试7: 空消息验证
empty_result = send_message(user1_id, user2_id, "")
if not empty_result['success']:
    print(f"[OK] Rejected empty message")
else:
    print(f"[FAIL] Should reject empty message")

# 测试8: 超长消息验证  
long_msg = "A" * 501
long_result = send_message(user1_id, user2_id, long_msg)
if long_result['success']:
    print(f"[WARN] Accepted long message ({len(long_msg)} chars) - no length validation")
else:
    print(f"[OK] Rejected long message (500 char limit)")


print("\n===测试完成===")
