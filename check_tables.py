#!/usr/bin/env python3
"""
簡化的數據庫表檢查腳本
"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def check_tables():
    database_url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    # 獲取所有表
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    existing = set(row[0] for row in cursor.fetchall())
    
    # 應該存在的表
    expected = {
        'audit_logs', 'boards', 'config_audit_log', 'conversation_history',
        'dm_conversations', 'dm_messages', 'forum_comments', 'friendships',
        'login_attempts', 'membership_payments', 'password_reset_tokens',
        'post_tags', 'posts', 'sessions', 'system_cache', 'system_config',
        'tags', 'tips', 'user_daily_comments', 'user_daily_posts',
        'user_message_limits', 'users', 'watchlist'
    }
    
    missing = expected - existing
    extra = existing - expected
    
    print(f"現有表數量: {len(existing)}")
    print(f"\n現有的表:")
    for t in sorted(existing):
        status = "✅" if t in expected else "📝"
        print(f"  {status} {t}")
    
    if missing:
        print(f"\n❌ 缺失的表 ({len(missing)} 個):")
        for t in sorted(missing):
            print(f"  - {t}")
    else:
        print(f"\n✅ 所有必需的表都存在！")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_tables()
