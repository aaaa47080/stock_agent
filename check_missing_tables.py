#!/usr/bin/env python3
"""
檢查數據庫缺失表的腳本
對比代碼中引用的表和數據庫中實際存在的表
"""
import os
import re
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def check_missing_tables():
    """檢查缺失的數據庫表"""
    
    database_url = os.getenv("DATABASE_URL")
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # 獲取數據庫中所有現有的表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        existing_tables = set(row[0] for row in cursor.fetchall())
        
        print("="*60)
        print("📊 數據庫表檢查報告")
        print("="*60)
        
        print(f"\n✅ 數據庫中現有的表 ({len(existing_tables)} 個):")
        for table in sorted(existing_tables):
            print(f"   - {table}")
        
        # 從 init_db() 代碼中提取應該存在的表
        expected_tables = {
            'watchlist',
            'system_cache',
            'system_config',
            'conversation_history',
            'sessions',
            'users',
            'membership_payments',
            'password_reset_tokens',
            'login_attempts',
            'boards',
            'posts',
            'forum_comments',
            'tips',
            'tags',
            'post_tags',
            'user_daily_comments',
            'user_daily_posts',
            'friendships',
            'dm_conversations',
            'dm_messages',
            'user_message_limits',
            'audit_logs',
            'config_audit_log',  # 從 system_config.py
        }
        
        # 檢查缺失的表
        missing_tables = expected_tables - existing_tables
        
        if missing_tables:
            print(f"\n⚠️  缺失的表 ({len(missing_tables)} 個):")
            for table in sorted(missing_tables):
                print(f"   ❌ {table}")
        else:
            print(f"\n✅ 所有必需的表都已存在！")
        
        # 檢查多餘的表（可能是舊的或測試用的）
        extra_tables = existing_tables - expected_tables
        if extra_tables:
            print(f"\n📝 其他表 ({len(extra_tables)} 個):")
            for table in sorted(extra_tables):
                print(f"   - {table}")
        
        # 檢查審計日誌視圖
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        views = [row[0] for row in cursor.fetchall()]
        if views:
            print(f"\n🔍 數據庫視圖 ({len(views)} 個):")
            for view in views:
                print(f"   - {view}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        if missing_tables:
            print("⚠️  發現缺失的表，需要進一步處理")
            return list(missing_tables)
        else:
            print("✅ 數據庫結構完整")
            return []
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    missing = check_missing_tables()
    if missing:
        print(f"\n建議: 重啟應用服務器讓 init_db() 自動創建缺失的表")
