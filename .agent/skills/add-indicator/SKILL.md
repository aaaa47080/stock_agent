---
name: Add Technical Indicator
description: How to add a new technical indicator to the data pipeline. Use when the user asks to add a new indicator (e.g., Stoch RSI, Williams %R, ATR, OBV, Ichimoku, etc.)
---

# Add a New Technical Indicator

## How the Data Pipeline Works

OKX API returns **raw OHLCV candle data only** — no indicators.
All indicators are calculated locally by `pandas_ta` after fetching.

```
OKX /market/candles
  → [timestamp, open, high, low, close, vol, ...]
      ↓
data/data_fetcher.py  (OKXDataFetcher.get_historical_klines)
  → DataFrame with columns: Open, High, Low, Close, Volume
      ↓
data/indicator_calculator.py  (add_technical_indicators)
  → pandas_ta appends indicator columns to df
  → e.g. df['RSI_14'], df['MACD_12_26_9'], df['SMA_7']
      ↓
data/data_processor.py  (extract_technical_indicators)
  → pulls the LATEST row values into a clean dict
  → e.g. {"RSI_14": 42.5, "MA_7": 45230, ...}
      ↓
market_data dict  (passed to all agents/LLMs)
```

**Key rule**: OKX gives OHLCV. We calculate everything else.

---

## Files to Change (Always These 4)

| File | What to Change |
|---|---|
| `data/indicator_calculator.py` | Add `df.ta.xxx(append=True)` |
| `data/data_processor.py` | Add key to `extract_technical_indicators()` dict |
| `core/agents/agents/tech_agent.py` | Add to `_build_signals()` and `_parse_indicators()` |
| `core/tools/crypto_tools.py` | Update the formatted output string (shown to user) |

---

## Step 1: Calculate the indicator — `data/indicator_calculator.py`

```python
def add_technical_indicators(df):
    # ... existing indicators ...

    # ADD NEW INDICATOR HERE — use pandas_ta
    df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)
    # → adds columns: STOCHRSIk_14_14_3_3, STOCHRSId_14_14_3_3

    return df
```

**Find the correct pandas_ta column name:**
```python
import pandas_ta as ta
help(ta.stochrsi)   # shows output column names
# OR run once and print: df.columns.tolist()
```

Common pandas_ta column name patterns:
- RSI → `RSI_14`
- MACD line → `MACD_12_26_9`
- Bollinger upper → `BBU_20_2.0_2.0` (note: period appears twice)
- Stochastic K → `STOCHk_14_3_3`
- Stoch RSI K → `STOCHRSIk_14_14_3_3`
- Williams %R → `WILLR_14`
- ATR → `ATRr_14`
- OBV → `OBV`
- Ichimoku → `ITS_9`, `IKS_26`, `ISA_9`, `ISB_26`

---

## Step 2: Extract the latest value — `data/data_processor.py`

```python
def extract_technical_indicators(latest_data: pd.Series) -> Dict[str, float]:
    return {
        # ... existing entries ...
        "RSI_14":      safe_float(latest_data.get('RSI_14', 50)),
        "MACD_線":     safe_float(latest_data.get('MACD_12_26_9', 0)),
        "MA_7":        safe_float(latest_data.get('SMA_7', 0)),
        "MA_25":       safe_float(latest_data.get('SMA_25', 0)),
        "布林帶上軌":   safe_float(latest_data.get('BBU_20_2.0_2.0', 0)),
        "布林帶下軌":   safe_float(latest_data.get('BBL_20_2.0_2.0', 0)),

        # NEW: add here — use the exact pandas_ta column name
        "StochRSI_K":  safe_float(latest_data.get('STOCHRSIk_14_14_3_3', 50)),
        "StochRSI_D":  safe_float(latest_data.get('STOCHRSId_14_14_3_3', 50)),
    }
```

**Important**: Use `safe_float()` and always provide a sensible default (50 for oscillators, 0 for others). The key name here is what flows into `market_data["技術指標"]`.

---

## Step 3: Add pre-computed signal text — `core/agents/agents/tech_agent.py`

**Do NOT let the LLM compare numbers.** Compute the signal in Python and pass the result text to the LLM. This prevents hallucination.

### 3a: Parse the indicator in `_parse_indicators()`

```python
def _parse_indicators(self, raw) -> dict:
    # ... existing parsing ...

    # If raw is a dict (already extracted), it flows through directly.
    # If raw is a Markdown string from V3 tools, add a regex for new indicator:
    stochrsi_match = re.search(r'StochRSI[_\s]*K[:\s]*([\d.]+)', raw)
    if stochrsi_match:
        parsed['StochRSI_K'] = stochrsi_match.group(1)
```

### 3b: Add signal logic in `_build_signals()`

```python
def _build_signals(self, indicators: dict) -> str:
    signals = []

    # ... existing MA / RSI / MACD signals ...

    # NEW: Stoch RSI signal
    stochrsi_k = indicators.get("StochRSI_K")
    if stochrsi_k:
        try:
            k = float(stochrsi_k)
            if k > 80:
                signals.append(f"StochRSI K ({k:.1f}) 超買區，動能可能轉弱")
            elif k < 20:
                signals.append(f"StochRSI K ({k:.1f}) 超賣區，動能可能回升")
            else:
                signals.append(f"StochRSI K ({k:.1f}) 中性區間")
        except (ValueError, TypeError):
            pass

    return "\n".join(f"- {s}" for s in signals) if signals else "（無可用訊號數據）"
```

---

## Step 4: Update formatted output for users — `core/tools/crypto_tools.py`

In `technical_analysis_tool`, find where the result string is built and add the new indicator to the displayed table.

Look for the section that builds the Markdown string and add:
```python
# In the formatted output string:
f"| StochRSI K | {indicators.get('StochRSI_K', 'N/A')} |"
```

---

## Step 5: Verify

```bash
# Quick check that the column exists after calculation
python -c "
from data.data_fetcher import get_data_fetcher
from data.indicator_calculator import add_technical_indicators
f = get_data_fetcher('okx')
df = f.get_historical_klines('BTC-USDT', '1d', limit=50)
df = add_technical_indicators(df)
print([c for c in df.columns if 'STOCH' in c.upper()])
print(df.iloc[-1][['RSI_14', 'STOCHRSIk_14_14_3_3']])
"
```

---

## Current Indicators Already in System

| Indicator | pandas_ta column | dict key in market_data |
|---|---|---|
| RSI (14) | `RSI_14` | `RSI_14` |
| MACD line | `MACD_12_26_9` | `MACD_線` |
| Bollinger Upper | `BBU_20_2.0_2.0` | `布林帶上軌` |
| Bollinger Lower | `BBL_20_2.0_2.0` | `布林帶下軌` |
| MA7 | `SMA_7` | `MA_7` |
| MA25 | `SMA_25` | `MA_25` |
| ADX | `ADX_14` | (not extracted yet) |
| Stochastic K | `STOCHk_14_3_3` | (not extracted yet) |
| OBV | `OBV` | (not extracted yet) |
| ATR | `ATRr_14` | (not extracted yet) |

Indicators marked "(not extracted yet)" are **already calculated** in `indicator_calculator.py`
but not pulled into `extract_technical_indicators()` — they just need Step 2 to be exposed.

---

## Anti-Hallucination Rule

The LLM must never compare two numbers by itself. Always:

```
❌ Wrong: feed raw numbers, ask LLM "is MA7 above MA25?"
✅ Right: compare in Python, feed "MA7 (45230) 高於 MA25 (42800)，短期偏多"
```

All new signals should be added to `_build_signals()` as pre-computed text strings,
not as raw numbers in the prompt.
