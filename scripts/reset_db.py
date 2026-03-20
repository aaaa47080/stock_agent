"""
reset_db.py — 重建資料庫表結構（會清空所有資料）

用法：
    python scripts/reset_db.py          # 重建表結構
    python scripts/reset_db.py --dry-run # 乾跑，只列出會刪除的表
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not found")
        sys.exit(1)

    # 移除不支援的參數
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params.pop("channel_binding", None)
    new_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=new_query))

    return psycopg2.connect(clean_url, connect_timeout=30)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="重建資料庫表結構")
    parser.add_argument("--dry-run", action="store_true", help="乾跑模式")
    args = parser.parse_args()

    conn = get_conn()
    c = conn.cursor()

    print("=" * 60)
    print("  資料庫表重建腳本")
    print("=" * 60)
    print(f"  模式: {'dry-run（不執行）' if args.dry_run else '執行'}")
    print()

    # 列出現有表
    c.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    existing = [row[0] for row in c.fetchall()]
    print(f"  現有表 ({len(existing)} 張):")
    for t in existing:
        print(f"    - {t}")
    print()

    if args.dry_run:
        print("  [DRY-RUN] 會執行以下操作:")
        print("    DROP SCHEMA public CASCADE;")
        print("    CREATE SCHEMA public;")
        print()
        print("  然後會呼叫 init_db() 重建所有表")
        conn.close()
        return

    # 刪除所有表（使用 schema cascade）
    print("  刪除所有表...")
    try:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
        # 恢復 public schema 的權限
        c.execute("GRANT ALL ON SCHEMA public TO public")
        conn.commit()
        print("    ✓ 所有表已刪除")
    except Exception as e:
        conn.rollback()
        print(f"    ✗ 刪除失敗: {e}")
        conn.close()
        return

    # 重建表
    print("  重建表結構...")
    conn.close()

    # 重置連接池並重建
    import core.database.connection as conn_module

    conn_module._connection_pool = None
    conn_module._db_initialized = False

    conn_module.init_db()
    print("    ✓ 表結構重建完成")

    # 驗證
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    count = c.fetchone()[0]
    print(f"\n  完成！共建立 {count} 張表")
    conn.close()


if __name__ == "__main__":
    main()
