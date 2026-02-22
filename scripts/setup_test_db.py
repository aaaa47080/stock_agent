"""
setup_test_db.py — 測試 DB 快速初始化腳本

用法：
    # 用 .env 裡的 DATABASE_URL
    python scripts/setup_test_db.py

    # 指定新的 DB URL（不會改寫 .env）
    python scripts/setup_test_db.py --url "postgresql://user:pass@host:5432/dbname"

    # 只建表，不建測試帳號
    python scripts/setup_test_db.py --skip-seed

    # 乾跑：只列出會做什麼，不真的執行
    python scripts/setup_test_db.py --dry-run

測試帳號（密碼都是 test1234）：
    admin     / test1234  → role=admin,  membership=pro（不過期）
    test_free / test1234  → role=user,   membership=free
    test_pro  / test1234  → role=user,   membership=pro（30天後到期）
    test_pi   （Pi 帳號）  → auth=pi_network, pi_uid=test_pi_uid_001
"""

import os
import sys
import argparse
import uuid
import hashlib
import psycopg2

# Windows terminal encoding fix
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── 確保 project root 在 sys.path ──────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ══════════════════════════════════════════════════════════════════════════════
# 輔助函數
# ══════════════════════════════════════════════════════════════════════════════

def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    key  = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + ':' + key.hex()


def _strip_unsupported_params(url: str) -> str:
    """移除 psycopg2 不支援的 URL 參數（如 channel_binding）。"""
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    # psycopg2 不支援 channel_binding，交由 SSL 協商處理
    params.pop("channel_binding", None)
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


def _get_conn(url: str):
    clean_url = _strip_unsupported_params(url)
    return psycopg2.connect(
        clean_url,
        connect_timeout=30,   # Neon cold start 最長約 20s
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )


def _ok(msg):   print(f"  [OK]   {msg}")
def _skip(msg): print(f"  [SKIP] {msg}")
def _info(msg): print(f"  [INFO] {msg}")
def _err(msg):  print(f"  [ERR]  {msg}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════════════════
# Step 1：建立所有資料表（直接呼叫 init_db）
# ══════════════════════════════════════════════════════════════════════════════

def create_tables(url: str, dry_run: bool):
    print("\n[Step 1] 建立資料表 (CREATE TABLE IF NOT EXISTS)...")
    if dry_run:
        _info("dry-run: 會呼叫 core.database.connection.init_db()")
        return

    # 暫時覆蓋環境變數，讓 init_db 使用正確的 URL
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url

    try:
        # 重置連接池狀態，避免舊 URL 的快取
        import core.database.connection as conn_module
        conn_module._connection_pool  = None
        conn_module._db_initialized   = False
        conn_module.DATABASE_URL      = url

        conn_module.init_db()
        _ok("所有資料表建立完成")
    finally:
        if original_url is not None:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)


# ══════════════════════════════════════════════════════════════════════════════
# Step 2：建立測試帳號（冪等：帳號已存在就跳過）
# ══════════════════════════════════════════════════════════════════════════════

TEST_ACCOUNTS = [
    {
        "username":    "admin",
        "password":    "test1234",
        "role":        "admin",
        "tier":        "pro",
        "expires":     "NOW() + INTERVAL '10 years'",
        "auth_method": "password",
        "note":        "管理員帳號（pro，10年不過期）",
    },
    {
        "username":    "test_free",
        "password":    "test1234",
        "role":        "user",
        "tier":        "free",
        "expires":     None,
        "auth_method": "password",
        "note":        "免費會員測試帳號",
    },
    {
        "username":    "test_pro",
        "password":    "test1234",
        "role":        "user",
        "tier":        "pro",
        "expires":     "NOW() + INTERVAL '30 days'",
        "auth_method": "password",
        "note":        "PRO 會員測試帳號（30天後到期）",
    },
    {
        "username":    "test_pi",
        "password":    None,
        "role":        "user",
        "tier":        "free",
        "expires":     None,
        "auth_method": "pi_network",
        "pi_uid":      "test_pi_uid_001",
        "note":        "Pi Network 測試帳號",
    },
]


def create_test_accounts(url: str, dry_run: bool):
    print("\n[Step 2] 建立測試帳號...")

    if dry_run:
        for acc in TEST_ACCOUNTS:
            _info(f"dry-run: 會建立 [{acc['username']}]  {acc['note']}")
        return

    conn = _get_conn(url)
    c    = conn.cursor()

    try:
        for acc in TEST_ACCOUNTS:
            username = acc["username"]

            # 檢查是否已存在
            c.execute("SELECT user_id, role, membership_tier FROM users WHERE username = %s", (username,))
            existing = c.fetchone()

            if existing:
                _skip(f"{username:12s} 已存在（role={existing[1]}, tier={existing[2]}），跳過")
                continue

            user_id  = str(uuid.uuid4())
            pwd_hash = _hash_password(acc["password"]) if acc.get("password") else None
            pi_uid   = acc.get("pi_uid")
            expires  = acc.get("expires")   # SQL fragment or None

            if expires:
                c.execute(f"""
                    INSERT INTO users
                        (user_id, username, password_hash, auth_method, pi_uid, pi_username,
                         role, membership_tier, membership_expires_at, is_active, created_at)
                    VALUES
                        (%s, %s, %s, %s, %s, %s,
                         %s, %s, {expires}, TRUE, NOW())
                """, (
                    user_id, username, pwd_hash,
                    acc["auth_method"], pi_uid, pi_uid,
                    acc["role"], acc["tier"],
                ))
            else:
                c.execute("""
                    INSERT INTO users
                        (user_id, username, password_hash, auth_method, pi_uid, pi_username,
                         role, membership_tier, is_active, created_at)
                    VALUES
                        (%s, %s, %s, %s, %s, %s,
                         %s, %s, TRUE, NOW())
                """, (
                    user_id, username, pwd_hash,
                    acc["auth_method"], pi_uid, pi_uid,
                    acc["role"], acc["tier"],
                ))

            conn.commit()
            _ok(f"{username:12s} 已建立  {acc['note']}")

    except Exception as e:
        conn.rollback()
        _err(f"建立帳號失敗: {e}")
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Step 3：驗證（列出建立結果）
# ══════════════════════════════════════════════════════════════════════════════

def verify(url: str, dry_run: bool):
    print("\n[Step 3] 驗證結果...")
    if dry_run:
        _info("dry-run: 跳過驗證")
        return

    conn = _get_conn(url)
    c    = conn.cursor()
    try:
        # 列出 users
        c.execute("""
            SELECT username, role, auth_method, membership_tier,
                   CASE WHEN membership_expires_at IS NULL THEN '-'
                        ELSE TO_CHAR(membership_expires_at, 'YYYY-MM-DD')
                   END AS expires,
                   is_active
            FROM users
            ORDER BY created_at
        """)
        rows = c.fetchall()
        if rows:
            print(f"\n  {'username':14s} {'role':8s} {'auth':12s} {'tier':6s} {'expires':12s} active")
            print(f"  {'-'*14} {'-'*8} {'-'*12} {'-'*6} {'-'*12} ------")
            for r in rows:
                print(f"  {str(r[0]):14s} {str(r[1]):8s} {str(r[2]):12s} {str(r[3]):6s} {str(r[4]):12s} {r[5]}")
        else:
            _info("users 表為空")

        # 列出 table 數量
        c.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        table_count = c.fetchone()[0]
        print(f"\n  總計建立 {table_count} 張資料表")

    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="初始化測試 DB：建立所有資料表 + 測試帳號",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--url",
        help="目標 DATABASE_URL（不填則使用 .env / 環境變數）",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="只建表，不建測試帳號",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="乾跑模式：只列出會做的事，不真的執行",
    )
    args = parser.parse_args()

    # 決定 DATABASE_URL
    if args.url:
        db_url = args.url
    else:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
        db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        _err("找不到 DATABASE_URL！請用 --url 參數或在 .env 設定")
        sys.exit(1)

    # 隱藏密碼用於顯示
    display_url = db_url
    if "@" in db_url:
        try:
            scheme, rest = db_url.split("://", 1)
            creds, host  = rest.split("@", 1)
            user         = creds.split(":")[0]
            display_url  = f"{scheme}://{user}:****@{host}"
        except Exception:
            pass

    print("=" * 60)
    print("  測試 DB 初始化腳本")
    print("=" * 60)
    print(f"  目標 DB : {display_url}")
    print(f"  模式    : {'dry-run（不執行）' if args.dry_run else '執行'}")
    print(f"  建測試帳: {'否' if args.skip_seed else '是'}")

    # 測試連線
    if not args.dry_run:
        print("\n[連線測試]")
        try:
            conn = _get_conn(db_url)
            conn.close()
            _ok("連線成功")
        except Exception as e:
            _err(f"無法連線: {e}")
            sys.exit(1)

    # 執行步驟
    create_tables(db_url, args.dry_run)

    if not args.skip_seed:
        create_test_accounts(db_url, args.dry_run)

    verify(db_url, args.dry_run)

    print("\n" + "=" * 60)
    print("  完成！" if not args.dry_run else "  dry-run 完成，未做任何變更")
    print("=" * 60)


if __name__ == "__main__":
    main()
