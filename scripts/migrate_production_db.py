#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Database Migration Script
同步正式版資料庫到最新 schema 結構

主要變更：
1. 移除 price_data 工具（重複工具造成 bug）
2. 會員等級整合：plus → premium
3. 更新 tools_catalog 的 tier_required 欄位
4. 更新使用者會員等級記錄
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def get_db_connection():
    """使用環境變數建立資料庫連線"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        # 從環境變數讀取資料庫連線資訊
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except ImportError:
        print("❌ psycopg2 未安裝，請先安裝: pip install psycopg2-binary")
        sys.exit(1)

def check_current_schema(conn):
    """檢查目前資料庫的 schema 狀態"""
    print("\n" + "="*60)
    print("📊 檢查目前資料庫 Schema")
    print("="*60)

    cur = conn.cursor()

    # 1. 檢查 tools_catalog table
    print("\n1️⃣ tools_catalog Table 結構:")
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'tools_catalog'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    for col in columns:
        print(f"   - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")

    # 2. 檢查是否有 price_data 工具
    print("\n2️⃣ 檢查 price_data 工具:")
    cur.execute("SELECT * FROM tools_catalog WHERE tool_id = 'price_data'")
    price_data = cur.fetchone()
    if price_data:
        print(f"   ⚠️  發現 price_data 工具 (tier_required: {price_data['tier_required']})")
    else:
        print("   ✅ price_data 工具已移除")

    # 3. 檢查 tier_required 欄位的值
    print("\n3️⃣ 檢查 tier_required 欄位值分佈:")
    cur.execute("""
        SELECT tier_required, COUNT(*) as count
        FROM tools_catalog
        GROUP BY tier_required
        ORDER BY tier_required
    """)
    tier_counts = cur.fetchall()
    for tier in tier_counts:
        print(f"   - {tier['tier_required']}: {tier['count']} 個工具")

    # 4. 檢查 agent_tool_permissions 中的 price_data
    print("\n4️⃣ 檢查 agent_tool_permissions 中的 price_data:")
    cur.execute("SELECT * FROM agent_tool_permissions WHERE tool_id = 'price_data'")
    permissions = cur.fetchall()
    if permissions:
        print(f"   ⚠️  發現 {len(permissions)} 筆 price_data 權限記錄")
        for perm in permissions:
            print(f"      - agent: {perm['agent_id']}, enabled: {perm['is_enabled']}")
    else:
        print("   ✅ agent_tool_permissions 中無 price_data 記錄")

    # 5. 檢查 user_memberships 中的等級記錄（表可能不存在）
    print("\n5️⃣ 檢查 user_memberships 中的等級記錄:")
    try:
        cur.execute("""
            SELECT membership_tier, COUNT(*) as count
            FROM user_memberships
            GROUP BY membership_tier
            ORDER BY membership_tier
        """)
        membership_counts = cur.fetchall()
        if membership_counts:
            for tier in membership_counts:
                print(f"   - {tier['membership_tier']}: {tier['count']} 個使用者")
        else:
            print("   ℹ️  user_memberships 表中無記錄")
    except Exception as e:
        print(f"   ℹ️  user_memberships 表不存在或無法查詢: {e}")
        conn.rollback()  # Reset transaction state

    # 6. 檢查 user_tool_preferences 中的設定
    print("\n6️⃣ 檢查 user_tool_preferences 中的設定:")
    cur.execute("""
        SELECT COUNT(*) as total
        FROM user_tool_preferences
        WHERE tool_id = 'price_data'
    """)
    price_data_prefs = cur.fetchone()['total']
    if price_data_prefs > 0:
        print(f"   ⚠️  發現 {price_data_prefs} 筆 price_data 使用者偏好設定")
    else:
        print("   ✅ user_tool_preferences 中無 price_data 記錄")

    cur.close()

def migrate_schema(conn, dry_run=True):
    """執行 schema 遷移"""
    print("\n" + "="*60)
    print(f"🚀 執行 Schema 遷移 ({'DRY RUN (模擬)' if dry_run else 'PRODUCTION (正式執行)'})")
    print("="*60)

    cur = conn.cursor()

    operations = []

    # 1. 移除 price_data 工具
    operations.append({
        'name': '移除 price_data 工具',
        'sql': "DELETE FROM tools_catalog WHERE tool_id = 'price_data'",
        'verify': "SELECT COUNT(*) FROM tools_catalog WHERE tool_id = 'price_data'"
    })

    # 2. 移除 agent_tool_permissions 中的 price_data
    operations.append({
        'name': '移除 agent_tool_permissions 中的 price_data',
        'sql': "DELETE FROM agent_tool_permissions WHERE tool_id = 'price_data'",
        'verify': "SELECT COUNT(*) FROM agent_tool_permissions WHERE tool_id = 'price_data'"
    })

    # 3. 移除 user_tool_preferences 中的 price_data
    operations.append({
        'name': '移除 user_tool_preferences 中的 price_data',
        'sql': "DELETE FROM user_tool_preferences WHERE tool_id = 'price_data'",
        'verify': "SELECT COUNT(*) FROM user_tool_preferences WHERE tool_id = 'price_data'"
    })

    # 4. 更新 tools_catalog 中的 tier_required: plus → premium
    operations.append({
        'name': '更新 tools_catalog tier_required: plus → premium',
        'sql': "UPDATE tools_catalog SET tier_required = 'premium' WHERE tier_required = 'plus'",
        'verify': "SELECT COUNT(*) FROM tools_catalog WHERE tier_required = 'plus'"
    })

    # 5. 更新 user_memberships 中的 membership_tier: plus → premium
    operations.append({
        'name': '更新 user_memberships membership_tier: plus → premium',
        'sql': "UPDATE user_memberships SET membership_tier = 'premium' WHERE membership_tier = 'plus'",
        'verify': "SELECT COUNT(*) FROM user_memberships WHERE membership_tier = 'plus'"
    })

    # 6. 更新 tools_catalog 中的 daily_limit_plus 欄位說明 (保持不變，僅供參考)
    operations.append({
        'name': '檢查 daily_limit_plus 欄位存在',
        'sql': "SELECT column_name FROM information_schema.columns WHERE table_name = 'tools_catalog' AND column_name = 'daily_limit_plus'",
        'verify': None  # 僅檢查，不修改
    })

    # 執行操作
    for i, op in enumerate(operations, 1):
        print(f"\n{i}. {op['name']}")
        print(f"   SQL: {op['sql']}")

        if dry_run:
            print("   ⏭️  [DRY RUN] 跳過執行")
        else:
            try:
                cur.execute(op['sql'])
                affected = cur.rowcount
                print(f"   ✅ 影響 {affected} 筆記錄")
                conn.commit()

                # 驗證結果
                if op['verify']:
                    cur.execute(op['verify'])
                    result = cur.fetchone()
                    if 'count' in result:
                        remaining = list(result.values())[0]
                        print(f"   📊 驗證: 剩餘 {remaining} 筆記錄")
            except Exception as e:
                print(f"   ❌ 執行失敗: {e}")
                conn.rollback()

    cur.close()

    if not dry_run:
        print("\n" + "="*60)
        print("✅ 遷移完成！")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("⚠️  這是 DRY RUN 模式，未實際修改資料庫")
        print("   如要正式執行，請使用: python migrate_production_db.py --execute")
        print("="*60)

def main():
    """主程式"""
    load_dotenv()

    # 檢查是否為正式執行模式
    dry_run = '--execute' not in sys.argv

    print("="*60)
    print("🔄 Production Database Migration Script")
    print("="*60)

    if dry_run:
        print("⚠️  DRY RUN 模式 - 不會實際修改資料庫")
    else:
        print("⚠️  PRODUCTION 模式 - 將實際修改資料庫！")

    try:
        # 建立資料庫連線
        conn = get_db_connection()
        print("✅ 資料庫連線成功")

        # 1. 檢查目前 schema
        check_current_schema(conn)

        # 2. 執行遷移
        migrate_schema(conn, dry_run=dry_run)

        # 關閉連線
        conn.close()
        print("\n✅ 資料庫連線已關閉")

    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
