"""
定時任務：遞減用戶違規點數
建議使用 cron 或 APScheduler 每天執行一次

功能：對30天內無新違規且上次遞減超過30天的用戶，每日自動遞減1點
"""
from datetime import datetime, timedelta
from core.database.connection import get_connection


def decrement_violation_points_job():
    """
    執行違規點數遞減任務

    每天 00:00 執行，為符合條件的用戶遞減 1 點

    條件：
    - 當前違規點數 > 0
    - 最後違規時間超過 30 天
    - 上次遞減時間超過 30 天（或從未遞減）

    返回：
        dict: 處理結果統計
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # 查詢符合條件的用戶
        c.execute('''
            SELECT user_id, points, last_violation_at, last_decrement_at
            FROM user_violation_points
            WHERE points > 0
              AND (last_decrement_at IS NULL OR last_decrement_at < NOW() - INTERVAL '30 days')
              AND (last_violation_at IS NULL OR last_violation_at < NOW() - INTERVAL '30 days')
            ORDER BY points DESC
        ''')

        users_to_decrement = c.fetchall()

        if not users_to_decrement:
            print("[Governance Cron] 沒有用戶需要遞減點數")
            return {
                "success": True,
                "processed_count": 0,
                "total_points_deducted": 0
            }

        # 執行遞減
        processed_count = 0
        total_points_deducted = 0

        for user_id, points, last_violation_at, last_decrement_at in users_to_decrement:
            # 確保點數不會變成負數
            new_points = max(0, points - 1)

            c.execute('''
                UPDATE user_violation_points
                SET points = %s,
                    last_decrement_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = %s
            ''', (new_points, user_id))

            # 記錄活動日誌
            c.execute('''
                INSERT INTO user_activity_logs
                (user_id, activity_type, resource_type, metadata, success, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            ''', (
                user_id,
                'points_decremented',
                'violation_points',
                '{"previous_points": %s, "new_points": %s, "decremented_by": 1}' % (points, new_points),
                True
            ))

            processed_count += 1
            total_points_deducted += 1

            print(f"[Governance Cron] 用戶 {user_id}: {points} -> {new_points} 點")

        conn.commit()

        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[Governance Cron] 執行時間: {current_time}")
        print(f"[Governance Cron] 處理 {processed_count} 個用戶，共遞減 {total_points_deducted} 點")

        return {
            "success": True,
            "processed_count": processed_count,
            "total_points_deducted": total_points_deducted
        }

    except Exception as e:
        print(f"[Governance Cron] 遞減點數失敗: {e}")
        conn.rollback()
        return {
            "success": False,
            "error": str(e),
            "processed_count": 0,
            "total_points_deducted": 0
        }
    finally:
        conn.close()


def cleanup_old_activity_logs(days_to_keep: int = 90):
    """
    清理舊的活動日誌

    Args:
        days_to_keep: 保留天數（默認 90 天）

    返回：
        int: 刪除的記錄數
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # 刪除超過保留期的日誌
        c.execute('''
            DELETE FROM user_activity_logs
            WHERE created_at < NOW() - INTERVAL '%s days'
        ''', (days_to_keep,))

        deleted_count = c.rowcount
        conn.commit()

        print(f"[Governance Cron] 清理了 {deleted_count} 條舊的活動日誌（超過 {days_to_keep} 天）")

        return deleted_count

    except Exception as e:
        print(f"[Governance Cron] 清理活動日誌失敗: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_governance_statistics():
    """
    獲取治理系統統計數據

    返回：
        dict: 統計數據
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        stats = {}

        # 違規點數統計
        c.execute('''
            SELECT
                COUNT(*) as total_users_with_points,
                SUM(points) as total_points,
                AVG(points) as avg_points,
                MAX(points) as max_points
            FROM user_violation_points
            WHERE points > 0
        ''')
        result = c.fetchone()
        if result:
            stats["users_with_points"] = result[0] or 0
            stats["total_points"] = result[1] or 0
            stats["avg_points"] = float(result[2]) if result[2] else 0
            stats["max_points"] = result[3] or 0

        # 活動日誌統計
        c.execute('''
            SELECT COUNT(*) FROM user_activity_logs
            WHERE created_at > NOW() - INTERVAL '7 days'
        ''')
        stats["recent_activity_logs"] = c.fetchone()[0] or 0

        return stats

    except Exception as e:
        print(f"[Governance Cron] 獲取統計數據失敗: {e}")
        return {}
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    print("=" * 50)
    print("社群治理系統 - 定時任務")
    print("=" * 50)

    # 執行點數遞減
    print("\n1. 執行違規點數遞減...")
    result = decrement_violation_points_job()

    # 清理舊日誌
    print("\n2. 清理舊的活動日誌...")
    deleted = cleanup_old_activity_logs(days_to_keep=90)

    # 獲取統計
    print("\n3. 獲取治理系統統計...")
    stats = get_governance_statistics()

    if stats:
        print(f"   - 有違規點數的用戶: {stats.get('users_with_points', 0)}")
        print(f"   - 總違規點數: {stats.get('total_points', 0)}")
        print(f"   - 平均點數: {stats.get('avg_points', 0):.2f}")
        print(f"   - 最高點數: {stats.get('max_points', 0)}")
        print(f"   - 近7天活動日誌: {stats.get('recent_activity_logs', 0)}")

    print("\n" + "=" * 50)
    print("定時任務完成")
    print("=" * 50)
