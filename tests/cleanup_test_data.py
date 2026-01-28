"""
清理测试数据并运行测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_connection

def cleanup():
    """清理所有测试数据"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 暂时禁用外键约束
        c.execute("PRAGMA foreign_keys = OFF")
        
        # 按照外键依赖顺序删除：先删除子表，后删除父表
        c.execute("DELETE FROM dm_messages WHERE from_user_id LIKE 'test_%' OR to_user_id LIKE 'test_%'")
        c.execute("DELETE FROM dm_conversations WHERE user1_id LIKE 'test_%' OR user2_id LIKE 'test_%'")
        c.execute("DELETE FROM user_message_limits WHERE user_id LIKE 'test_%'")
        c.execute("DELETE FROM friendships WHERE user_id LIKE 'test_%' OR friend_id LIKE 'test_%'")
        c.execute("DELETE FROM users WHERE user_id LIKE 'test_%' OR email LIKE 'test%@example.com'")
        conn.commit()
        
        # 重新启用外键约束
        c.execute("PRAGMA foreign_keys = ON")
        print("Test data cleaned successfully")
    except Exception as e:
        print(f"Error cleaning test data: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    cleanup()
