"""
定時任務：批量清理過期會員
建議使用 cron 或 APScheduler 每天執行一次
"""
from datetime import datetime
from core.database.connection import get_connection

def batch_expire_memberships():
    """
    批量處理過期會員
    每天 00:00 執行，將所有過期的 PRO 會員降級為 FREE
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 查詢過期會員數量
        c.execute('''
            SELECT COUNT(*) FROM users
            WHERE membership_tier = 'pro'
              AND membership_expires_at < NOW()
        ''')
        count_before = c.fetchone()[0]

        if count_before == 0:
            print(f"[Cron] 沒有過期會員需要處理")
            return

        # 批量更新過期會員
        c.execute('''
            UPDATE users
            SET membership_tier = 'free',
                membership_expires_at = NULL
            WHERE membership_tier = 'pro'
              AND membership_expires_at < NOW()
        ''')

        affected = c.rowcount
        conn.commit()

        print(f"[Cron] 成功處理 {affected} 個過期會員 (預期: {count_before})")

        # 記錄日誌（可選：存入數據庫）
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[Cron] 執行時間: {current_time}")

        return affected

    except Exception as e:
        print(f"[Cron] 批量處理過期會員失敗: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    # 測試執行
    batch_expire_memberships()
