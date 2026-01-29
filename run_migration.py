#!/usr/bin/env python3
"""
數據庫遷移腳本 - 創建審計日誌表
運行審計日誌遷移 SQL 腳本來創建必要的數據庫表和索引
"""
import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 載入環境變量
load_dotenv()

def run_migration():
    """執行審計日誌表遷移"""
    
    # 從環境變量獲取數據庫 URL
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ 錯誤: 找不到 DATABASE_URL 環境變量")
        print("請確保 .env 文件中設置了 DATABASE_URL")
        sys.exit(1)
    
    print("🔄 開始數據庫遷移...")
    print(f"📊 數據庫: {database_url.split('@')[1] if '@' in database_url else 'hidden'}")
    
    try:
        # 連接到數據庫
        print("\n📡 連接到數據庫...")
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # 讀取 SQL 遷移文件
        sql_file = "database/migrations/add_audit_logs.sql"
        print(f"\n📄 讀取遷移文件: {sql_file}")
        
        if not os.path.exists(sql_file):
            print(f"❌ 錯誤: 找不到遷移文件 {sql_file}")
            sys.exit(1)
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 執行 SQL 腳本
        print("\n⚙️  執行 SQL 遷移...")
        cursor.execute(sql_script)
        
        print("✅ SQL 腳本執行成功!")
        
        # 驗證表已創建
        print("\n🔍 驗證表創建...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'audit_logs'
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"✅ 表 'audit_logs' 已成功創建")
        else:
            print("⚠️  警告: 無法確認表是否創建")
        
        # 檢查索引
        cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'audit_logs'
        """)
        
        indexes = cursor.fetchall()
        if indexes:
            print(f"✅ 已創建 {len(indexes)} 個索引:")
            for idx in indexes[:5]:  # 只顯示前 5 個
                print(f"   - {idx[0]}")
            if len(indexes) > 5:
                print(f"   ... 還有 {len(indexes) - 5} 個索引")
        
        # 檢查視圖
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'v_%'
        """)
        
        views = cursor.fetchall()
        if views:
            print(f"✅ 已創建 {len(views)} 個視圖:")
            for view in views:
                print(f"   - {view[0]}")
        
        # 關閉連接
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✅ 遷移完成！審計日誌系統已就緒")
        print("="*60)
        print("\n下一步:")
        print("1. 重啟你的應用服務器")
        print("2. 審計日誌將自動開始記錄操作")
        print("\n查看審計日誌:")
        print("  SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;")
        
    except psycopg2.Error as e:
        print(f"\n❌ 數據庫錯誤: {e}")
        print(f"詳細信息: {e.pgerror if hasattr(e, 'pgerror') else str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("="*60)
    print("  數據庫遷移工具 - 審計日誌表")
    print("="*60)
    run_migration()
