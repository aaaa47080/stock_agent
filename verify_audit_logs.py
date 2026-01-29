#!/usr/bin/env python3
"""
簡單的數據庫驗證腳本 - 檢查 audit_logs 表
"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def verify_audit_logs():
    """驗證 audit_logs 表存在且結構正確"""
    
    database_url = os.getenv("DATABASE_URL")
    
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        print("🔍 驗證審計日誌表...")
        
        # 檢查表是否存在
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        if columns:
            print(f"\n✅ audit_logs 表存在，包含 {len(columns)} 個欄位:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
        else:
            print("❌ audit_logs 表不存在")
            return False
        
        # 檢查索引數量
        cursor.execute("""
            SELECT COUNT(*) 
            FROM pg_indexes 
            WHERE tablename = 'audit_logs'
        """)
        index_count = cursor.fetchone()[0]
        print(f"\n✅ 已創建 {index_count} 個索引")
        
        # 檢查視圖
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.views 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'v_%'
        """)
        view_count = cursor.fetchone()[0]
        print(f"✅ 已創建 {view_count} 個審計視圖")
        
        # 測試插入（然後刪除）
        print("\n🧪 測試寫入...")
        cursor.execute("""
            INSERT INTO audit_logs (action, endpoint, method, success)
            VALUES ('test_migration', '/test', 'GET', TRUE)
            RETURNING id
        """)
        test_id = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM audit_logs WHERE id = %s", (test_id,))
        conn.commit()
        print("✅ 寫入測試成功")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*60)
        print("✅ 所有驗證通過！審計日誌系統已就緒")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"\n❌ 驗證失敗: {e}")
        return False

if __name__ == "__main__":
    verify_audit_logs()
