#!/usr/bin/env python3
"""
Agent V4 交互式聊天介面 (LangGraph 版)

用法：
    python chat_v4.py                     # 互動模式
    python chat_v4.py "你好"              # 單次查詢
    python chat_v4.py --debug "BTC 分析"  # 顯示 classify/plan 詳細資訊

互動模式快捷指令：
    /help          — 說明
    /status        — Agent / Tool / Codebook 狀態
    /new           — 開啟新 session
    /session       — 顯示目前 session_id
    /debug on|off  — 切換 debug 模式
    /exit /quit    — 退出
"""
import sys
import os
import argparse
import traceback
from uuid import uuid4
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ── LLM 建立 ──────────────────────────────────────────────────────────────────

def build_llm():
    """從環境變數或 .env 讀取 API key，建立 LLM client。"""
    api_key  = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    provider = os.environ.get("LLM_PROVIDER", "openai")

    if not api_key:
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        if k.strip() in ("OPENAI_API_KEY", "LLM_API_KEY"):
                            api_key = v.strip().strip("'\"")
                            break

    if not api_key:
        print("❌  找不到 API Key。\n"
              "    請設定環境變數 OPENAI_API_KEY，或在 .env 加入 OPENAI_API_KEY=sk-...")
        sys.exit(1)

    from utils.user_client_factory import create_user_llm_client
    return create_user_llm_client(provider=provider, api_key=api_key)


# ── 查詢執行 ──────────────────────────────────────────────────────────────────

def run_query(manager, query: str, session_id: str, debug: bool = False) -> str:
    """
    執行單次查詢。
    debug=True 時，在 LLM 回應後印出 classify/plan 細節。
    """
    from langgraph.types import Command

    config  = {"configurable": {"thread_id": session_id}}
    initial = {
        "session_id":          session_id,
        "query":               query,
        "agent_results":       [],
        "user_clarifications": [],
        "retry_count":         0,
    }

    result = manager.graph.invoke(initial, config)

    if debug:
        _print_debug(result)

    # ── CLI HITL loop ──
    while result.get("__interrupt__"):
        iv       = result["__interrupt__"][0].value
        question = iv.get("question", "請回答：")
        options  = iv.get("options")
        print(f"\n🤔  {question}")
        if options:
            for i, o in enumerate(options, 1):
                print(f"    {i}. {o}")
        print()
        try:
            answer = input("你的回答 > ").strip()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        result = manager.graph.invoke(Command(resume=answer), config)
        if debug:
            _print_debug(result)

    return result.get("final_response") or "（無回應）"


def _print_debug(result: dict):
    print(f"\n  ┌─ [debug] ────────────────────────────────")
    print(f"  │  complexity : {result.get('complexity')}")
    print(f"  │  intent     : {result.get('intent')}")
    print(f"  │  topics     : {result.get('topics')}")
    for i, t in enumerate(result.get("plan") or []):
        print(f"  │  plan[{i}]    : [{t.get('agent')}] {t.get('description', '')[:60]}")
    print(f"  └──────────────────────────────────────────")


# ── 互動模式 ──────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════╗
║         🤖  Agent V4  —  LangGraph CLI 測試工具          ║
╠══════════════════════════════════════════════════════════╣
║  輸入問題直接送出，/help 查看指令                         ║
╚══════════════════════════════════════════════════════════╝"""

def interactive(manager, debug: bool):
    session_id = str(uuid4())
    print(BANNER)
    print(f"  session: {session_id[:8]}...\n")

    while True:
        try:
            query = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再見！")
            break

        if not query:
            continue

        if query in ("/exit", "/quit"):
            print("再見！")
            break
        elif query == "/help":
            print(
                "  /exit /quit    — 退出\n"
                "  /status        — Agent / Tool / Codebook 狀態\n"
                "  /new           — 開啟新 session\n"
                "  /session       — 顯示 session_id\n"
                "  /debug on|off  — 切換 debug 模式"
            )
        elif query == "/status":
            s = manager.get_status()
            print(f"  agents  : {s['agents']}")
            print(f"  tools   : {s['tools']}")
            print(f"  codebook: {s['codebook']}")
        elif query == "/new":
            session_id = str(uuid4())
            print(f"  新 session: {session_id[:8]}...")
        elif query == "/session":
            print(f"  session: {session_id}")
        elif query == "/debug on":
            debug = True
            print("  debug 已開啟")
        elif query == "/debug off":
            debug = False
            print("  debug 已關閉")
        else:
            try:
                response = run_query(manager, query, session_id, debug=debug)
                print(f"\n助手 > {response}\n")
            except Exception as e:
                print(f"\n❌ 錯誤: {e}\n")
                if debug:
                    traceback.print_exc()


# ── 入口 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="V4 Agent CLI 測試")
    parser.add_argument("query", nargs="?", help="單次查詢（省略則進入互動模式）")
    parser.add_argument("--debug", "-d", action="store_true", help="顯示 classify/plan 細節")
    args = parser.parse_args()

    print("載入 V4 Agent...", end=" ", flush=True)
    llm     = build_llm()
    from core.agents.bootstrap import bootstrap
    manager = bootstrap(llm, web_mode=False)  # CLI 模式：HITL 可讀 stdin
    print("✅\n")

    if args.query:
        session_id = str(uuid4())
        resp = run_query(manager, args.query, session_id, debug=args.debug)
        print(f"\n助手 > {resp}")
    else:
        interactive(manager, debug=args.debug)


if __name__ == "__main__":
    main()
