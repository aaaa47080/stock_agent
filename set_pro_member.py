#!/usr/bin/env python3
"""
給 test-user-002 設置 PRO 會員身分
"""

import os
import sys
from datetime import datetime, timedelta

# 添加專案路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from core.database.connection import get_connection

def grant_pro_membership(user_id: str = "test-user-002"):
    """給指定用戶設置永久 PRO 會員"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 檢查用戶是否存在
        cursor.execute("SELECT user_id, username FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ 用戶 {user_id} 不存在！")
            return False
        
        print(f"✅ 找到用戶: {user[1]} (ID: {user[0]})")
        
        # 設置到期時間為 10 年後（實際上就是永久）
        expires_at = datetime.now() + timedelta(days=3650)
        
        # 直接更新 users 表的 membership_tier 和 membership_expires_at
        cursor.execute("""
            UPDATE users 
            SET membership_tier = 'pro', 
                membership_expires_at = %s
            WHERE user_id = %s
        """, (expires_at, user_id))
        
        print(f"✅ 更新會員身分為 PRO（到期日: {expires_at.strftime('%Y-%m-%d')}）")
        
        conn.commit()
        
        # 驗證結果
        cursor.execute("""
            SELECT membership_tier, membership_expires_at 
            FROM users 
            WHERE user_id = %s
        """, (user_id,))
        result = cursor.fetchone()
        
        if result:
            print(f"\n🎉 成功！會員狀態:")
            print(f"   等級: {result[0]}")
            print(f"   到期: {result[1]}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    grant_pro_membership("test-user-002")
