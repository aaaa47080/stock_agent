# Multi-Market Agent Architecture Design

**Date:** 2026-02-20
**Scope:** Taiwan Stock + Universal Symbol Resolution + Agent Consolidation

---

## 1. Background & Motivation

Current system only supports crypto (Binance/OKX). Users want Taiwan stock analysis. Key insight from design session: a symbol like "TSM" could be crypto, TW stock (2330.TW), or US stock (NYSE:TSM). The system must handle ambiguity gracefully.

---

## 2. Final Architecture

```
Manager (LangGraph)
  ├── CryptoAgent     ← Merged TechAgent + NewsAgent (refactor)
  ├── TWStockAgent    ← New: all TW stock analysis
  ├── ChatAgent       ← Unchanged
  └── USStockAgent    ← New stub: detects US stocks, returns "coming soon"
```

Manager supports **parallel dispatch**: if UniversalSymbolResolver matches multiple markets, Manager calls multiple agents concurrently and Synthesis node presents results side-by-side.

---

## 3. Universal Symbol Resolver

Entry point before any routing. Checks all markets in parallel.

### Resolution Logic

```
Input: any string (e.g., "台積電", "TSM", "2330", "BTC")
       ↓
Step 1 — Format detection
  - Pure 4-6 digits → try TW stock (append .TW)
  - Contains .TW / .TWO suffix → TW stock directly
  - Known crypto pattern (3-5 uppercase, no digits) → try crypto
       ↓
Step 2 — Market resolution (all 3 in parallel)
  crypto_resolve(input)   → symbol or None
  tw_resolve(input)       → "XXXX.TW" or None
  us_resolve(input)       → "TICKER" or None
       ↓
Step 3 — Decision
  - Multiple markets matched → parallel dispatch
  - Single market matched   → route to that agent
  - No match               → return canned message ("查無此標的，請確認代號")
```

### TW Symbol Resolution Detail

```
① Digit check: "2330" → "2330.TW" ✓
② Name lookup: query tw_stock_list cache
   - Source: TWSE openapi.twse.com.tw/v1/opendata/t187ap03_L (listed)
             TPEX openapi.tpex.org.tw/v1/opendata/t187ap04_L (OTC)
   - Fields: 公司代號, 公司簡稱, 英文簡稱
   - Cache: system_cache key="tw_stock_list", TTL=24h
③ rapidfuzz fuzzy match on 公司簡稱 + 英文簡稱, threshold=80
④ LLM fallback (one-shot): only if fuzzy score < 80
⑤ Ambiguous: ask user to clarify
```

### Crypto Resolution

- Check against known exchange symbol lists (Binance/OKX top pairs)
- Pattern: 3-5 uppercase letters, no digits
- Examples: BTC, ETH, SOL → crypto; TSM → no match

### US Stock Resolution

- Simple pattern match: 1-5 uppercase letters on known US exchanges
- For now: basic heuristic (will be improved when USStockAgent is fully implemented)
- TSM → matches NYSE listing → `{us: "TSM"}`

---

## 4. CryptoAgent (Refactor of TechAgent + NewsAgent)

**Merges:** `tech_agent.py` + `news_agent.py` → `crypto_agent.py`

### Tools
| Tool | Source | Description |
|------|--------|-------------|
| `crypto_price` | Exchange API (Binance/OKX) | Real-time OHLCV |
| `crypto_technical` | Exchange OHLCV + pandas_ta | RSI, MACD, MA, KD |
| `crypto_news` | Google News RSS + CryptoCompare | News aggregation |

### Prompt
Combined from `tech_agent.yaml` + `news_agent.yaml`. Handles:
- Pure technical queries → run crypto_technical only
- Pure news queries → run crypto_news only
- Full analysis → run all three tools

---

## 5. TWStockAgent (New)

**File:** `core/agents/agents/tw_stock_agent.py`

### Tools
| Tool | Source | Description |
|------|--------|-------------|
| `tw_stock_price` | yfinance (primary), TWSE API (fallback) | Real-time + recent OHLCV |
| `tw_technical_analysis` | yfinance OHLCV + pandas_ta | RSI, MACD, KD, MA5/20/60 |
| `tw_fundamentals` | FinMind free tier → yfinance fallback | EPS, P/E, ROE |
| `tw_institutional` | TWSE openapi / FinMind | 外資/投信/自營商 chips |
| `tw_news` | Google News RSS (`{股票名} 股票`) | TW-specific news |

### Data Source Strategy (Free-first)
- **yfinance**: primary for price + technical data, no API key needed, ~15min delay
- **TWSE openapi**: stock list (daily cache) + institutional data (official)
- **FinMind free tier**: fundamentals, with rate limit fallback to yfinance financials
- **Google News RSS**: news (same pattern as existing crypto news tools)

### Analysis Flow
```
TWStockAgent.run(query, symbol="2330.TW")
  1. Classify query intent:
     - price/technical → tw_stock_price + tw_technical_analysis
     - fundamentals    → tw_fundamentals
     - institutional   → tw_institutional
     - news            → tw_news
     - full analysis   → all tools
  2. Invoke tools (parallel where possible)
  3. LLM synthesizes Chinese analysis report
```

---

## 6. USStockAgent (Stub)

**File:** `core/agents/agents/us_stock_agent.py`

Minimal stub implementation:
- Receives routed request for US stock symbol
- Returns: `"美股分析功能開發中，敬請期待。偵測到的標的：{symbol} (NYSE/NASDAQ)"`
- Placeholder for future full implementation

---

## 7. Manager Changes

### Parallel Dispatch Logic
```python
resolution = universal_resolver.resolve(user_input)
# resolution = {crypto: "BTC", tw: None, us: None}

if len(resolution.matches) > 1:
    # Parallel dispatch
    results = await asyncio.gather(*[
        agent_registry.get(market).run(query, symbol)
        for market, symbol in resolution.matches.items()
    ])
    return synthesis.combine_multi_market(results)
elif len(resolution.matches) == 1:
    market, symbol = next(iter(resolution.matches.items()))
    return agent_registry.get(market).run(query, symbol)
else:
    return "查無此標的，請確認股票代號或名稱。"
```

### Routing Keywords (Classification)
- TW stock signals: 台股、上市、上櫃、4-6 digit numbers, `.TW` suffix
- Crypto signals: BTC/ETH/crypto keywords, exchange names
- US stock signals: NYSE, NASDAQ, S&P, US company names

---

## 8. New File Structure

```
core/
  agents/
    agents/
      crypto_agent.py         ← NEW (replaces tech_agent.py + news_agent.py)
      tw_stock_agent.py       ← NEW
      us_stock_agent.py       ← NEW (stub)
      chat_agent.py           ← unchanged
    prompts/
      crypto_agent.yaml       ← NEW (merged prompt)
      tw_stock_agent.yaml     ← NEW
      us_stock_agent.yaml     ← NEW (stub)

core/tools/
  tw_stock_tools.py           ← NEW (5 @tool functions)
  tw_symbol_resolver.py       ← NEW (SymbolResolver class)
  universal_resolver.py       ← NEW (UniversalSymbolResolver)

core/database/
  (uses existing system_cache, no new tables needed)
```

---

## 9. Dependencies (New)

```
yfinance        # TW + US stock price data
rapidfuzz       # Fuzzy string matching for symbol resolution
pandas_ta       # Technical indicators (may already be present)
```

---

## 10. Error Handling & Fallbacks

| Scenario | Behavior |
|----------|----------|
| TWSE API down | Use cached list; if cache empty, LLM fallback |
| yfinance rate limit | Retry once; if fails, return last cached price with timestamp |
| FinMind quota exceeded | Fallback to yfinance `.info` fields for basic fundamentals |
| Symbol ambiguous | Show disambiguation prompt with top 3 candidates |
| No market match | Canned message: "查無此標的，請確認代號" |
| US stock detected | Stub response with symbol identified |

---

## 11. Out of Scope (This Phase)

- Real-time streaming quotes
- Portfolio tracking
- US stock full analysis (stub only)
- Backtesting for TW stocks
- Alert/notification system
