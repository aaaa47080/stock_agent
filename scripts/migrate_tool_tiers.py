"""
遷移腳本：將所有 tier_required='plus' 的工具更新為 'premium'
執行方式: python scripts/migrate_tool_tiers.py
"""

import os
import sys

# 將專案根目錄加入 Python 路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.database.connection import get_connection


def migrate_tool_tiers():
    """將所有 plus 等級工具更新為 premium"""
    conn = get_connection()
    c = conn.cursor()

    try:
        # 查詢目前有多少 plus 等級的工具
        c.execute("""
            SELECT tool_id, display_name, tier_required
            FROM tools_catalog
            WHERE tier_required = 'plus'
        """)
        plus_tools = c.fetchall()

        if not plus_tools:
            print("✅ 沒有找到 'plus' 等級的工具，資料庫已經是最新狀態")
            return

        print(f"📊 找到 {len(plus_tools)} 個 'plus' 等級的工具需要更新:")
        for tool_id, display_name, _ in plus_tools:
            print(f"  - {tool_id}: {display_name}")

        # 更新所有 plus 為 premium
        c.execute("""
            UPDATE tools_catalog
            SET tier_required = 'premium'
            WHERE tier_required = 'plus'
        """)

        conn.commit()
        print(f"\n✅ 成功更新 {len(plus_tools)} 個工具的等級為 'premium'")

    except Exception as e:
        conn.rollback()
        print(f"❌ 遷移失敗: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("🔄 開始遷移工具等級...")
    migrate_tool_tiers()
    print("✨ 遷移完成！")
