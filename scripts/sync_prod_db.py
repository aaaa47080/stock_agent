#!/usr/bin/env python3
"""
sync_prod_db.py — 同步正式環境資料庫表結構

這個腳本會：
1. 在正式環境創建所有表（使用 CREATE TABLE IF NOT EXISTS）
2. 標記 alembic 版本為最新

用法：
    python scripts/sync_prod_db.py          # 執行同步
    python scripts/sync_prod_db.py --dry-run # 乾跑
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))


def get_conn(url: str):
    """獲取資料庫連線"""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params.pop("channel_binding", None)
    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))
    return psycopg2.connect(clean_url, connect_timeout=30)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="同步正式環境資料庫")
    parser.add_argument("--dry-run", action="store_true", help="乾跑模式")
    args = parser.parse_args()

    prod_url = os.environ.get("PROD_DATABASE_URL")
    if not prod_url:
        print("❌ PROD_DATABASE_URL 未設定")
        sys.exit(1)

    # 隱藏密碼
    display_url = prod_url
    if "@" in prod_url:
        try:
            scheme, rest = prod_url.split("://", 1)
            creds, host = rest.split("@", 1)
            user = creds.split(":")[0]
            display_url = f"{scheme}://{user}:****@{host}"
        except Exception:
            pass  # URL parse error - display_url remains unchanged

    print("=" * 60)
    print("  正式環境資料庫同步")
    print("=" * 60)
    print(f"  目標 DB: {display_url}")
    print(f"  模式: {'乾跑（不執行）' if args.dry_run else '執行'}")
    print()

    # 測試連線
    print("🔌 測試連線...")
    try:
        conn = get_conn(prod_url)
        c = conn.cursor()
        c.execute("SELECT 1")
        c.close()
        print("  ✓ 連線成功")
    except Exception as e:
        print(f"  ✗ 連線失敗: {e}")
        sys.exit(1)

    if args.dry_run:
        print()
        print("📋 乾跑模式 - 會執行以下操作:")
        print("  1. 呼叫 init_db() 創建/更新所有表")
        print("  2. 創建 alembic_version 表並標記為最新版本")
        print("  3. 創建所有索引")
        conn.close()
        return

    # 同步表結構
    print()
    print("📊 同步表結構...")
    conn.close()

    # 暫時覆蓋 DATABASE_URL，讓 init_db 使用正式環境
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = prod_url

    try:
        import core.database.connection as conn_module

        conn_module._connection_pool = None
        conn_module._db_initialized = False
        conn_module.DATABASE_URL = prod_url

        conn_module.init_db()
        print("  ✓ 表結構同步完成")
    finally:
        if original_url:
            os.environ["DATABASE_URL"] = original_url

    # 標記 alembic 版本
    print()
    print("🏷️ 標記 Alembic 版本...")
    conn = get_conn(prod_url)
    c = conn.cursor()

    # 創建 alembic_version 表（如果不存在）
    c.execute("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(32) NOT NULL PRIMARY KEY
        )
    """)

    # 清除並插入最新版本
    c.execute("DELETE FROM alembic_version")
    c.execute("INSERT INTO alembic_version (version_num) VALUES ('4107b7e75608')")

    conn.commit()
    print("  ✓ 已標記為版本 4107b7e75608")

    # 驗證
    print()
    print("✅ 驗證...")
    c.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    count = c.fetchone()[0]
    print(f"  正式環境共有 {count} 張表")

    c.execute("SELECT version_num FROM alembic_version")
    version = c.fetchone()
    print(f"  Alembic 版本: {version[0] if version else 'None'}")

    conn.close()
    print()
    print("=" * 60)
    print("  ✅ 同步完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
