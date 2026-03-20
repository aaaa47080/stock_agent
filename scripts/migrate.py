#!/usr/bin/env python3
"""
migrate.py — 資料庫 Migration 管理腳本

用法：
    python scripts/migrate.py status              # 查看當前 migration 狀態
    python scripts/migrate.py upgrade             # 升級到最新版本
    python scripts/migrate.py downgrade           # 回退一個版本
    python scripts/migrate.py revision "message"  # 創建新的 migration
    python scripts/migrate.py stamp               # 標記當前資料庫為最新版本
    python scripts/migrate.py --prod upgrade      # 對正式環境執行
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def run_alembic(args: list, db_url: str = None):
    """執行 alembic 命令"""
    env = os.environ.copy()
    if db_url:
        env["DATABASE_URL"] = db_url

    cmd = [sys.executable, "-m", "alembic"] + args
    result = subprocess.run(cmd, cwd=ROOT, env=env)
    return result.returncode


def main():
    import argparse

    parser = argparse.ArgumentParser(description="資料庫 Migration 管理")
    parser.add_argument(
        "command",
        choices=["status", "upgrade", "downgrade", "revision", "stamp", "history"],
        help="要執行的命令",
    )
    parser.add_argument("message", nargs="?", help="migration 訊息（用於 revision）")
    parser.add_argument("--prod", action="store_true", help="對正式環境執行")
    parser.add_argument("--dev", action="store_true", help="對開發環境執行（預設）")
    args = parser.parse_args()

    # 載入環境變數
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))

    # 決定使用的資料庫 URL
    if args.prod:
        db_url = os.environ.get("PROD_DATABASE_URL")
        if not db_url:
            print("❌ PROD_DATABASE_URL 未設定")
            sys.exit(1)
        env_name = "正式環境"
    else:
        db_url = os.environ.get("DATABASE_URL")
        env_name = "開發環境"

    print(f"🔍 目標環境: {env_name}")
    print()

    # 執行命令
    if args.command == "status":
        print("📊 Migration 狀態:")
        run_alembic(["current"], db_url)

    elif args.command == "upgrade":
        print("⬆️ 升級到最新版本:")
        run_alembic(["upgrade", "head"], db_url)

    elif args.command == "downgrade":
        print("⬇️ 回退一個版本:")
        run_alembic(["downgrade", "-1"], db_url)

    elif args.command == "revision":
        if not args.message:
            print("❌ 請提供 migration 訊息")
            sys.exit(1)
        print(f"📝 創建新 migration: {args.message}")
        run_alembic(["revision", "-m", args.message], db_url)

    elif args.command == "stamp":
        print("🏷️ 標記為最新版本:")
        run_alembic(["stamp", "head"], db_url)

    elif args.command == "history":
        print("📜 Migration 歷史:")
        run_alembic(["history"], db_url)


if __name__ == "__main__":
    main()
