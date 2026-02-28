"""
工具系統資料庫操作
包含：工具目錄管理、Agent 工具權限、用戶工具偏好、使用量追蹤
"""
from typing import List, Dict, Optional
from .connection import get_connection


# ============================================================================
# 工具目錄 Seed 資料
# ============================================================================

_TOOLS_SEED = [
    # ── Crypto 基礎 ─────────────────────────────────────────────────────────
    {
        "tool_id": "get_crypto_price",
        "display_name": "即時加密貨幣價格",
        "description": "查詢加密貨幣即時價格",
        "category": "crypto_basic",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "get_current_time_taipei",
        "display_name": "目前時間",
        "description": "查詢台灣/UTC+8 目前時間",
        "category": "general",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "get_fear_and_greed_index",
        "display_name": "恐慌與貪婪指數",
        "description": "查詢全球加密貨幣市場恐慌貪婪指數",
        "category": "crypto_basic",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "get_trending_tokens",
        "display_name": "熱門幣種排行",
        "description": "查詢全網最熱門搜尋的加密貨幣",
        "category": "crypto_basic",
        "tier_required": "free",
        "quota_type": "shared_limited",
        "daily_limit_free": 20,
        "daily_limit_prem": None,
    },
    # ── Crypto 技術分析 ─────────────────────────────────────────────────────
    {
        "tool_id": "technical_analysis",
        "display_name": "加密貨幣技術指標",
        "description": "RSI、MACD、均線等技術指標分析",
        "category": "technical",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "price_data",
        "display_name": "加密貨幣歷史 K 線",
        "description": "即時與歷史 OHLCV 價格數據",
        "category": "technical",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    # ── 新聞 ────────────────────────────────────────────────────────────────
    {
        "tool_id": "google_news",
        "display_name": "Google 新聞",
        "description": "從 Google News 抓取相關新聞",
        "category": "news",
        "tier_required": "free",
        "quota_type": "shared_limited",
        "daily_limit_free": 30,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "aggregate_news",
        "display_name": "多來源新聞聚合",
        "description": "從多個來源聚合加密貨幣新聞",
        "category": "news",
        "tier_required": "free",
        "quota_type": "shared_limited",
        "daily_limit_free": 20,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "web_search",
        "display_name": "網路搜尋",
        "description": "DuckDuckGo 通用網路搜尋",
        "category": "general",
        "tier_required": "free",
        "quota_type": "shared_limited",
        "daily_limit_free": 20,
        "daily_limit_prem": None,
    },
    # ── Crypto 衍生品（Premium）───────────────────────────────────────────
    {
        "tool_id": "get_futures_data",
        "display_name": "合約資金費率",
        "description": "查詢永續合約資金費率與多空情緒",
        "category": "derivatives",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    # ── Crypto 鏈上數據（Premium）─────────────────────────────────────────
    {
        "tool_id": "get_defillama_tvl",
        "display_name": "DeFi TVL 鎖倉量",
        "description": "從 DefiLlama 查詢協議/公鏈 TVL",
        "category": "onchain",
        "tier_required": "premium",
        "quota_type": "shared_limited",
        "daily_limit_free": 0,
        "daily_limit_prem": 50,
    },
    {
        "tool_id": "get_crypto_categories_and_gainers",
        "display_name": "加密板塊與漲幅排行",
        "description": "CoinGecko 最強板塊與熱點",
        "category": "onchain",
        "tier_required": "premium",
        "quota_type": "shared_limited",
        "daily_limit_free": 0,
        "daily_limit_prem": 30,
    },
    {
        "tool_id": "get_token_unlocks",
        "display_name": "代幣解鎖日程",
        "description": "查詢代幣未來解鎖時間與數量",
        "category": "onchain",
        "tier_required": "premium",
        "quota_type": "shared_limited",
        "daily_limit_free": 0,
        "daily_limit_prem": 50,
    },
    {
        "tool_id": "get_token_supply",
        "display_name": "代幣流通供應量",
        "description": "查詢代幣總發行量、最大供應量與流通量",
        "category": "onchain",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    # ── 台股 基礎 ───────────────────────────────────────────────────────────
    {
        "tool_id": "tw_stock_price",
        "display_name": "台股即時股價",
        "description": "查詢台灣股票即時價格",
        "category": "tw_stock",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_technical_analysis",
        "display_name": "台股技術指標",
        "description": "台股 RSI / MACD / KD / 均線",
        "category": "tw_stock",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_news",
        "display_name": "台股新聞",
        "description": "查詢台股相關最新新聞",
        "category": "tw_stock",
        "tier_required": "free",
        "quota_type": "shared_limited",
        "daily_limit_free": 20,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_major_news",
        "display_name": "台股重大訊息",
        "description": "TWSE 官方重大訊息公告",
        "category": "tw_stock",
        "tier_required": "free",
        "quota_type": "shared_limited",
        "daily_limit_free": 20,
        "daily_limit_prem": None,
    },
    # ── 台股 進階（Premium）─────────────────────────────────────────────────
    {
        "tool_id": "tw_fundamentals",
        "display_name": "台股基本面",
        "description": "P/E、EPS、ROE 等基本面資料",
        "category": "tw_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_institutional",
        "display_name": "台股法人籌碼",
        "description": "外資、投信、自營商三大法人買賣超",
        "category": "tw_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_pe_ratio",
        "display_name": "台股本益比",
        "description": "P/E 比、股息殖利率、P/B 比",
        "category": "tw_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_monthly_revenue",
        "display_name": "台股月營收",
        "description": "月營收數據含 MoM、YoY 成長率",
        "category": "tw_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_dividend",
        "display_name": "台股股利",
        "description": "現金股利、股票股利、除權息日期",
        "category": "tw_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "tw_foreign_top20",
        "display_name": "外資持股 Top 20",
        "description": "外資與陸資持股前 20 名排行",
        "category": "tw_stock",
        "tier_required": "premium",
        "quota_type": "shared_limited",
        "daily_limit_free": 0,
        "daily_limit_prem": 30,
    },
    # ── 美股 基礎 ───────────────────────────────────────────────────────────
    {
        "tool_id": "us_stock_price",
        "display_name": "美股即時股價",
        "description": "美股即時價格（15 分鐘延遲，Yahoo Finance）",
        "category": "us_stock",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "us_technical_analysis",
        "display_name": "美股技術指標",
        "description": "美股 RSI / MACD / 布林帶 / 均線",
        "category": "us_stock",
        "tier_required": "free",
        "quota_type": "unlimited",
        "daily_limit_free": None,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "us_news",
        "display_name": "美股新聞",
        "description": "美股相關最新新聞",
        "category": "us_stock",
        "tier_required": "free",
        "quota_type": "shared_limited",
        "daily_limit_free": 20,
        "daily_limit_prem": None,
    },
    # ── 美股 進階（Premium）─────────────────────────────────────────────────
    {
        "tool_id": "us_fundamentals",
        "display_name": "美股基本面",
        "description": "P/E、EPS、ROE、市值、股息率",
        "category": "us_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "us_earnings",
        "display_name": "美股財報",
        "description": "財報數據與財報日曆",
        "category": "us_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "us_institutional_holders",
        "display_name": "美股機構持倉",
        "description": "機構投資人持倉數據",
        "category": "us_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
    {
        "tool_id": "us_insider_transactions",
        "display_name": "美股內部人交易",
        "description": "公司內部人買賣記錄",
        "category": "us_stock",
        "tier_required": "premium",
        "quota_type": "unlimited",
        "daily_limit_free": 0,
        "daily_limit_prem": None,
    },
]

# Agent 預設工具清單（bootstrap.py 的 fallback）
_AGENT_DEFAULT_TOOLS: Dict[str, List[str]] = {
    "crypto": [
        "get_current_time_taipei", "technical_analysis", "price_data", "get_crypto_price",
        "google_news", "aggregate_news", "web_search",
        "get_fear_and_greed_index", "get_trending_tokens", "get_futures_data",
        "get_defillama_tvl", "get_crypto_categories_and_gainers", "get_token_unlocks", "get_token_supply",
    ],
    "tw_stock": [
        "get_current_time_taipei", "tw_stock_price", "tw_technical_analysis",
        "tw_fundamentals", "tw_institutional", "tw_news", "tw_major_news",
        "tw_pe_ratio", "tw_monthly_revenue", "tw_dividend", "tw_foreign_top20", "web_search",
    ],
    "us_stock": [
        "us_stock_price", "us_technical_analysis", "us_fundamentals",
        "us_earnings", "us_news", "us_institutional_holders",
        "us_insider_transactions", "get_current_time_taipei",
    ],
    "chat": [
        "get_current_time_taipei", "get_crypto_price", "web_search",
    ],
}


# ============================================================================
# DB 操作函數
# ============================================================================

def seed_tools_catalog():
    """
    首次執行時把所有工具 metadata 寫入 tools_catalog 和 agent_tool_permissions。
    使用 INSERT ... ON CONFLICT DO NOTHING 確保冪等（可重複執行）。
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Seed tools_catalog
        for t in _TOOLS_SEED:
            c.execute('''
                INSERT INTO tools_catalog
                    (tool_id, display_name, description, category,
                     tier_required, quota_type, daily_limit_free, daily_limit_prem, source_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'native')
                ON CONFLICT (tool_id) DO NOTHING
            ''', (
                t["tool_id"], t["display_name"], t["description"], t["category"],
                t["tier_required"], t["quota_type"],
                t["daily_limit_free"], t["daily_limit_prem"],
            ))

        # 2. Seed agent_tool_permissions
        for agent_id, tools in _AGENT_DEFAULT_TOOLS.items():
            for tool_id in tools:
                c.execute('''
                    INSERT INTO agent_tool_permissions (agent_id, tool_id, is_enabled)
                    VALUES (%s, %s, TRUE)
                    ON CONFLICT (agent_id, tool_id) DO NOTHING
                ''', (agent_id, tool_id))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[tools] seed_tools_catalog error: {e}")
    finally:
        conn.close()


def get_allowed_tools(agent_id: str, user_tier: str = "free", user_id: Optional[str] = None) -> List[str]:
    """
    取得某 agent 對特定用戶可用的工具清單。

    過濾邏輯（三層）：
    1. tools_catalog.is_active = TRUE
    2. agent_tool_permissions.is_enabled = TRUE
    3. tools_catalog.tier_required <= user_tier
       (premium 用戶可用全部；free 用戶只能用 tier_required='free')
    4. （可選）用戶偏好：user_tool_preferences.is_enabled = FALSE 的排除

    若 DB 資料為空（首次啟動前尚未 seed），回傳 hardcode fallback。
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 組合 tier 條件
        if user_tier == "premium":
            tier_condition = "tc.tier_required IN ('free', 'premium')"
        else:
            tier_condition = "tc.tier_required = 'free'"

        query = f'''
            SELECT tc.tool_id
            FROM tools_catalog tc
            JOIN agent_tool_permissions atp
                ON tc.tool_id = atp.tool_id AND atp.agent_id = %s
            WHERE tc.is_active = TRUE
              AND atp.is_enabled = TRUE
              AND {tier_condition}
        '''

        # 排除用戶主動關閉的工具（Premium 功能）
        if user_id and user_tier == "premium":
            query = f'''
                SELECT tc.tool_id
                FROM tools_catalog tc
                JOIN agent_tool_permissions atp
                    ON tc.tool_id = atp.tool_id AND atp.agent_id = %s
                LEFT JOIN user_tool_preferences utp
                    ON tc.tool_id = utp.tool_id AND utp.user_id = %s
                WHERE tc.is_active = TRUE
                  AND atp.is_enabled = TRUE
                  AND {tier_condition}
                  AND (utp.is_enabled IS NULL OR utp.is_enabled = TRUE)
            '''
            c.execute(query, (agent_id, user_id))
        else:
            c.execute(query, (agent_id,))

        rows = c.fetchall()

        # Fallback：DB 還沒 seed 時用 hardcode 清單
        if not rows:
            return _get_fallback_tools(agent_id, user_tier)

        return [row[0] for row in rows]

    except Exception as e:
        print(f"[tools] get_allowed_tools error: {e}")
        return _get_fallback_tools(agent_id, user_tier)
    finally:
        conn.close()


def _get_fallback_tools(agent_id: str, user_tier: str) -> List[str]:
    """DB 不可用時的 hardcode fallback（與原 bootstrap.py 一致）"""
    all_tools = _AGENT_DEFAULT_TOOLS.get(agent_id, [])
    if user_tier == "premium":
        return all_tools
    # Free 用戶只拿 seed 資料中 tier_required='free' 的
    free_tool_ids = {t["tool_id"] for t in _TOOLS_SEED if t["tier_required"] == "free"}
    return [t for t in all_tools if t in free_tool_ids]


def check_tool_quota(user_id: str, tool_id: str, user_tier: str) -> bool:
    """
    檢查用戶今日對某工具是否還有額度。
    回傳 True = 可以使用；False = 已達上限。
    unlimited 或 premium 且 daily_limit_prem is None 一律回傳 True。
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            SELECT quota_type, daily_limit_free, daily_limit_prem
            FROM tools_catalog WHERE tool_id = %s AND is_active = TRUE
        ''', (tool_id,))
        row = c.fetchone()

        if not row:
            return True  # 找不到 → 不限制

        quota_type, limit_free, limit_prem = row

        if quota_type == "unlimited":
            return True

        limit = limit_prem if user_tier == "premium" else limit_free
        if limit is None:
            return True   # NULL = 無限
        if limit == 0:
            return False  # 0 = 完全不開放

        # 查今日使用量
        c.execute('''
            SELECT call_count FROM tool_usage_log
            WHERE user_id = %s AND tool_id = %s AND used_date = CURRENT_DATE
        ''', (user_id, tool_id))
        usage_row = c.fetchone()
        used = usage_row[0] if usage_row else 0

        return used < limit

    except Exception as e:
        print(f"[tools] check_tool_quota error: {e}")
        return True  # 錯誤時放行，不影響用戶體驗
    finally:
        conn.close()


def increment_tool_usage(user_id: str, tool_id: str):
    """記錄工具呼叫一次（upsert）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO tool_usage_log (user_id, tool_id, used_date, call_count)
            VALUES (%s, %s, CURRENT_DATE, 1)
            ON CONFLICT (user_id, tool_id, used_date)
            DO UPDATE SET call_count = tool_usage_log.call_count + 1
        ''', (user_id, tool_id))
        conn.commit()
    except Exception as e:
        print(f"[tools] increment_tool_usage error: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_tools_for_frontend(user_tier: str, user_id: Optional[str] = None) -> List[Dict]:
    """
    回傳前端設定頁需要的工具清單。
    包含每個工具的 display_name、category、tier_required、
    以及用戶當前的 is_enabled 狀態（Premium 才有個人偏好）。
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        if user_id and user_tier == "premium":
            c.execute('''
                SELECT tc.tool_id, tc.display_name, tc.description, tc.category,
                       tc.tier_required, tc.quota_type,
                       COALESCE(utp.is_enabled, TRUE) AS is_enabled
                FROM tools_catalog tc
                LEFT JOIN user_tool_preferences utp
                    ON tc.tool_id = utp.tool_id AND utp.user_id = %s
                WHERE tc.is_active = TRUE
                ORDER BY tc.category, tc.tier_required, tc.tool_id
            ''', (user_id,))
        else:
            c.execute('''
                SELECT tool_id, display_name, description, category,
                       tier_required, quota_type, TRUE AS is_enabled
                FROM tools_catalog
                WHERE is_active = TRUE
                ORDER BY category, tier_required, tool_id
            ''')

        rows = c.fetchall()
        return [
            {
                "tool_id": r[0],
                "display_name": r[1],
                "description": r[2],
                "category": r[3],
                "tier_required": r[4],
                "quota_type": r[5],
                "is_enabled": r[6],
                "locked": r[4] == "premium" and user_tier != "premium",
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[tools] get_tools_for_frontend error: {e}")
        return []
    finally:
        conn.close()


def update_user_tool_preference(user_id: str, tool_id: str, is_enabled: bool):
    """更新用戶對某工具的個人偏好（僅 Premium 可用）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO user_tool_preferences (user_id, tool_id, is_enabled, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id, tool_id)
            DO UPDATE SET is_enabled = EXCLUDED.is_enabled, updated_at = NOW()
        ''', (user_id, tool_id, is_enabled))
        conn.commit()
    except Exception as e:
        print(f"[tools] update_user_tool_preference error: {e}")
        conn.rollback()
    finally:
        conn.close()
