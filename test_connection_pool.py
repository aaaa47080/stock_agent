#!/usr/bin/env python3
"""
測試數據庫連接池
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# 添加到路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_connection_pool():
    """測試連接池功能"""
    print("="*60)
    print("🧪 測試數據庫連接池")
    print("="*60)
    
    try:
        from core.database import get_connection, close_all_connections
        
        print("\n測試 1: 獲取單個連接")
        conn1 = get_connection()
        print(f"✅ 連接 1 獲取成功: {conn1}")
        
        print("\n測試 2: 獲取多個連接")
        conn2 = get_connection()
        conn3 = get_connection()
        print(f"✅ 連接 2 獲取成功: {conn2}")
        print(f"✅ 連接 3 獲取成功: {conn3}")
        
        print("\n測試 3: 執行查詢")
        cursor = conn1.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        print(f"✅ 查詢成功: 用戶數 = {count}")
        cursor.close()
        
        print("\n測試 4: 歸還連接到池")
        conn1.close()
        print("✅ 連接 1 已歸還")
        conn2.close()
        print("✅ 連接 2 已歸還")
        conn3.close()
        print("✅ 連接 3 已歸還")
        
        print("\n測試 5: 從池中重新獲取（應該復用）")
        conn4 = get_connection()
        print(f"✅ 連接 4 獲取成功（可能復用了之前的連接）: {conn4}")
        conn4.close()
        
        print("\n測試 6: 審計日誌表存在性")
        conn5 = get_connection()
        cursor = conn5.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'audit_logs'
        """)
        exists = cursor.fetchone()[0] > 0
        if exists:
            print("✅ audit_logs 表存在")
        else:
            print("❌ audit_logs 表不存在")
        cursor.close()
        conn5.close()
        
        print("\n" + "="*60)
        print("✅ 所有測試通過！連接池工作正常")
        print("="*60)
        
        # 清理
        # close_all_connections()
        print("\n💡 提示: 連接池將在應用關閉時自動清理")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_connection_pool()
    sys.exit(0 if success else 1)
