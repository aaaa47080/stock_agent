import sys
import os
# Add the project root directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from tqdm import tqdm
import pandas as pd
import time
import json

# Import project-specific modules
from data.data_fetcher import get_data_fetcher, SymbolNotFoundError
from data.indicator_calculator import add_technical_indicators
from core.graph import app, AgentState
from core.config import DEFAULT_INTERVAL, DEFAULT_KLINES_LIMIT, CRYPTO_CURRENCIES_TO_ANALYZE, DEFAULT_FUTURES_LEVERAGE
from core.models import TraderDecision
from trading.okx_api_connector import OKXAPIConnector

def convert_symbol_format(symbol: str, source_exchange: str, target_exchange: str) -> str:
    """
    Converts symbol format between different exchanges.
    Binance/OKX format conversion:
    - Binance: BTCUSDT, ETHUSDT (no separator)
    - OKX: BTC-USDT, ETH-USDT (with hyphen separator)
    """
    source_exchange = source_exchange.lower()
    target_exchange = target_exchange.lower()

    # If same exchange, return original symbol
    if source_exchange == target_exchange:
        return symbol

    # Convert from Binance format to OKX format
    if source_exchange in ['binance'] and target_exchange in ['okx']:
        if 'USDT' in symbol:
            base_currency = symbol.replace('USDT', '')
            return f"{base_currency}-USDT"
        elif 'BTC' in symbol and symbol.endswith('BTC'):  # For BTC pairs like ETHBTC
            base_currency = symbol.replace('BTC', '')
            return f"{base_currency}-BTC"
        elif 'ETH' in symbol and symbol.endswith('ETH'):  # For ETH pairs like LINKETH
            base_currency = symbol.replace('ETH', '')
            return f"{base_currency}-ETH"
        else:
            # If it's a different quote currency, handle generically
            for quote in ['USDC', 'USD', 'EUR', 'GBP', 'BTC', 'ETH']:
                if symbol.endswith(quote):
                    base_currency = symbol.replace(quote, '')
                    return f"{base_currency}-{quote}"

    # Convert from OKX format to Binance format
    elif source_exchange in ['okx'] and target_exchange in ['binance']:
        return symbol.replace('-', '')

    # Default: return original symbol if no conversion is needed
    return symbol

async def run_full_analysis(exchange_name: str, market_type: str = 'spot', leverage: int = 1, limit: int = None, progress=None, custom_symbols: list = None, exchange_fallback: list = None, include_account_balance: bool = True):
    """
    Runs a full analysis on a specified list of symbols or top N symbols from a given exchange.

    Args:
        exchange_name (str): The primary exchange ('Binance' or 'OKX').
        market_type (str): The market type ('spot' or 'futures'). Defaults to 'spot'.
        leverage (int): The leverage for futures trading. Defaults to 1 for spot.
        limit (int, optional): The number of top symbols to analyze if custom_symbols is not provided.
                               Defaults to None, in which case all symbols from CRYPTO_CURRENCIES_TO_ANALYZE are used.
        progress (gradio.Progress): Gradio progress tracker.
        custom_symbols (list, optional): A list of symbols to analyze. If provided, overrides CRYPTO_CURRENCIES_TO_ANALYZE.
        exchange_fallback (list, optional): List of fallback exchanges to try if the primary exchange doesn't have the symbol.
        include_account_balance (bool): Whether to retrieve account balance information. Defaults to True.

    Returns:
        list: A list of dictionaries, where each dictionary is the analysis result for a symbol.
    """
    if progress:
        progress(0, desc="Initializing...")

    # If exchange_fallback is not provided, use default fallback list
    if exchange_fallback is None:
        exchange_fallback = ["okx", "binance"]  # Default fallback order
        # Remove the primary exchange from fallback list
        exchange_fallback = [ex for ex in exchange_fallback if ex.lower() != exchange_name.lower()]

    # Determine the list of symbols to analyze
    if custom_symbols:
        symbols_to_analyze = custom_symbols
    else:
        symbols_to_analyze = CRYPTO_CURRENCIES_TO_ANALYZE
        if limit and limit > 0: # If a limit is specified, use only that many from the configured list
            symbols_to_analyze = symbols_to_analyze[:limit]


    if not symbols_to_analyze:
        print("No symbols configured for analysis.")
        return {"error": "No symbols configured for analysis. Please check CRYPTO_CURRENCIES_TO_ANALYZE in config.py or provide custom_symbols."}

    # Retrieve account balance information if requested
    account_balance_info = None
    if include_account_balance and exchange_name.lower() == 'okx':
        try:
            okx_connector = OKXAPIConnector()
            # Get account balance in USDT
            balance_response = okx_connector.get_account_balance("USDT")
            if balance_response.get("code") == "0":
                balance_data = balance_response.get("data", [])
                if balance_data and len(balance_data) > 0:
                    details = balance_data[0].get("details", [])
                    if details:
                        usdt_balance = details[0]
                        total_balance = float(usdt_balance.get("eq", 0))
                        available_balance = float(usdt_balance.get("availEq", 0))
                        account_balance_info = {
                            "total_balance": total_balance,
                            "available_balance": available_balance,
                            "currency": "USDT"
                        }
                        print(f"Account balance retrieved: Total = ${total_balance}, Available = ${available_balance}")
            else:
                print(f"Failed to retrieve account balance: {balance_response.get('msg', 'Unknown error')}")
        except Exception as e:
            print(f"Error retrieving account balance: {str(e)}")
            account_balance_info = None

    # 2. Iterate and analyze each symbol
    all_results = []
    total_symbols = len(symbols_to_analyze)

    # Using tqdm for console progress, which will be tracked by Gradio's progress object
    for i, symbol in enumerate(tqdm(symbols_to_analyze, desc="Analyzing Symbols")):
        start_progress = 0.05
        end_progress = 0.95
        current_progress = start_progress + (i / total_symbols) * (end_progress - start_progress)

        if progress:
            progress(current_progress, desc=f"Analyzing {symbol} ({i+1}/{total_symbols})")

        # Try the primary exchange first
        exchange_to_use = exchange_name
        fetcher = None
        df = None
        funding_rate_info = {}

        # Try primary exchange
        try:
            fetcher = get_data_fetcher(exchange_name)

            # Convert symbol format based on the target exchange
            symbol_for_primary_exchange = convert_symbol_format(symbol, "binance", exchange_name.lower())  # Convert from binance format to target exchange format
            print(f"Using symbol format '{symbol_for_primary_exchange}' for {exchange_name}")

            if market_type == 'futures':
                df, funding_rate_info = fetcher.get_futures_data(symbol_for_primary_exchange, DEFAULT_INTERVAL, limit=DEFAULT_KLINES_LIMIT)
            else:
                df = fetcher.get_historical_klines(symbol_for_primary_exchange, DEFAULT_INTERVAL, limit=DEFAULT_KLINES_LIMIT)

            # Update symbol to reflect the format used on this exchange
            symbol = symbol_for_primary_exchange
        except SymbolNotFoundError as e:
            print(f"Symbol {symbol} not found on primary exchange {exchange_name}: {e}")
            # Try fallback exchanges
            for fallback_exchange in exchange_fallback:
                try:
                    print(f"Trying fallback exchange: {fallback_exchange}")
                    fetcher = get_data_fetcher(fallback_exchange)

                    # Convert symbol format from original (binance) format to target exchange format
                    symbol_for_exchange = convert_symbol_format(symbol, "binance", fallback_exchange)  # Convert from binance format to target exchange format
                    print(f"Using symbol format '{symbol_for_exchange}' for {fallback_exchange}")

                    if market_type == 'futures':
                        df, funding_rate_info = fetcher.get_futures_data(symbol_for_exchange, DEFAULT_INTERVAL, limit=DEFAULT_KLINES_LIMIT)
                    else:
                        df = fetcher.get_historical_klines(symbol_for_exchange, DEFAULT_INTERVAL, limit=DEFAULT_KLINES_LIMIT)

                    if df is not None and not df.empty:
                        exchange_to_use = fallback_exchange
                        symbol = symbol_for_exchange  # Update symbol to the format used
                        print(f"Found {symbol_for_exchange} on {fallback_exchange}")
                        break
                except SymbolNotFoundError:
                    continue
                except Exception as e:
                    print(f"Error trying fallback exchange {fallback_exchange}: {e}")
                    continue
        except Exception as e:
            print(f"Error with primary exchange {exchange_name}: {e}")
            # Try fallback exchanges
            for fallback_exchange in exchange_fallback:
                try:
                    print(f"Trying fallback exchange: {fallback_exchange}")
                    fetcher = get_data_fetcher(fallback_exchange)

                    # Convert symbol format from original (binance) format to target exchange format
                    symbol_for_exchange = convert_symbol_format(symbol, "binance", fallback_exchange)  # Convert from binance format to target exchange format
                    print(f"Using symbol format '{symbol_for_exchange}' for {fallback_exchange}")

                    if market_type == 'futures':
                        df, funding_rate_info = fetcher.get_futures_data(symbol_for_exchange, DEFAULT_INTERVAL, limit=DEFAULT_KLINES_LIMIT)
                    else:
                        df = fetcher.get_historical_klines(symbol_for_exchange, DEFAULT_INTERVAL, limit=DEFAULT_KLINES_LIMIT)

                    if df is not None and not df.empty:
                        exchange_to_use = fallback_exchange
                        symbol = symbol_for_exchange  # Update symbol to the format used
                        print(f"Found {symbol_for_exchange} on {fallback_exchange}")
                        break
                except SymbolNotFoundError:
                    continue
                except Exception as e:
                    print(f"Error trying fallback exchange {fallback_exchange}: {e}")
                    continue

        if df is None or df.empty:
            print(f"Skipping {symbol}: No K-line data returned from any exchange.")
            all_results.append({
                "symbol": symbol,
                "signal": "ERROR",
                "reasoning": f"Symbol '{symbol}' not found on {exchange_name} or any fallback exchange.",
                "market_type": market_type  # Add market type to result
            })
            continue

        # Process data and calculate indicators
        df_with_indicators = add_technical_indicators(df)

        # Fetch news data (similar to chat_interface.py logic)
        base_currency = symbol.replace("USDT", "").replace("BUSD", "").replace("-", "").replace("SWAP", "")

        # Simulating the same data structure as in chat_interface.py
        latest = df_with_indicators.iloc[-1]
        current_price = latest['Close']

        # Recent 5 days history
        recent_history = []
        recent_days = min(5, len(df_with_indicators))
        for i in range(-recent_days, 0):
            day_data = df_with_indicators.iloc[i]
            recent_history.append({
                "日期": i, "開盤": day_data['Open'], "最高": day_data['High'],
                "最低": day_data['Low'], "收盤": day_data['Close'], "交易量": day_data['Volume']
            })

        # Key levels (last 30 days)
        recent_30 = df_with_indicators.tail(30) if len(df_with_indicators) >= 30 else df_with_indicators
        key_levels = {
            "30天最高價": recent_30['High'].max(), "30天最低價": recent_30['Low'].min(),
            "支撐位": recent_30['Low'].quantile(0.25), "壓力位": recent_30['High'].quantile(0.75),
        }

        # Market structure
        price_changes = df_with_indicators['Close'].pct_change()
        market_structure = {
            "趨勢": "上漲" if price_changes.tail(7).mean() > 0 else "下跌",
            "波動率": (price_changes.tail(30).std() * 100) if len(price_changes) >= 30 else 0,
            "平均交易量": df_with_indicators['Volume'].tail(7).mean(),
        }

        # Prepare initial state for the graph with the same structure as chat_interface
        preloaded_data_dict = {
            "market_type": market_type,
            "exchange": exchange_to_use,
            "leverage": leverage,
            "funding_rate_info": funding_rate_info,
            "價格資訊": {
                "當前價格": current_price,
                "7天價格變化百分比": ((latest['Close'] / df_with_indicators.iloc[-7]['Close']) - 1) * 100 if len(df_with_indicators) >= 7 else 0,
            },
            "技術指標": {
                "RSI_14": latest.get('RSI_14', 0),
                "MACD_線": latest.get('MACD_12_26_9', 0),
                "布林帶上軌": latest.get('BB_upper_20_2', 0),
                "布林帶下軌": latest.get('BB_lower_20_2', 0),
                "MA_7": latest.get('MA_7', 0),
                "MA_25": latest.get('MA_25', 0),
            },
            "最近5天歷史": recent_history,
            "市場結構": market_structure,
            "關鍵價位": key_levels,
            "新聞資訊": None  # Batch mode doesn't include news for now
        }

        # Add account balance information if available
        if account_balance_info:
            preloaded_data_dict["account_balance"] = account_balance_info

        initial_state = AgentState(
            symbol=symbol,
            exchange=exchange_to_use,
            interval=DEFAULT_INTERVAL,
            limit=DEFAULT_KLINES_LIMIT,
            market_type=market_type,  # Now configurable (spot or futures)
            leverage=leverage,  # Configurable leverage
            preloaded_data=preloaded_data_dict,
            client=None,  # Will be initialized in node
            market_data={},  # Will be populated in node
            current_price=current_price,
            funding_rate_info=funding_rate_info,
            analyst_reports=[],
            bull_argument=None,
            bear_argument=None,
            trader_decision=None,
            risk_assessment=None,
            final_approval=None,
            replan_count=0,
            messages=[]
        )

        # Invoke the analysis graph
        # The graph is synchronous, but we run it in a way that doesn't block the UI event loop
        # by using asyncio.to_thread if this function was async. Since Gradio handles this, direct call is fine.
        final_state = app.invoke(initial_state, {"recursion_limit": 15})

        # Extract result
        if final_state and final_state.get('trader_decision'):
            decision : TraderDecision = final_state['trader_decision']
            result = {
                "symbol": symbol,
                "signal": decision.decision,
                "confidence": decision.confidence,
                "entry_price": decision.entry_price,
                "stop_loss": decision.stop_loss,
                "take_profit": decision.take_profit,
                "reasoning": decision.reasoning,
                "market_type": market_type,  # Add market type to result
                "exchange": exchange_to_use  # Add exchange used to result
            }
            # Add account balance information if available in preloaded data
            if initial_state.get('preloaded_data') and initial_state['preloaded_data'].get('account_balance'):
                result["account_balance"] = initial_state['preloaded_data']['account_balance']
            all_results.append(result)
        else:
             all_results.append({
                "symbol": symbol,
                "signal": "ERROR",
                "reasoning": "Analysis did not produce a final decision.",
                "market_type": market_type,  # Add market type to result
                "exchange": exchange_to_use,  # Add exchange used to result
                "account_balance": initial_state.get('preloaded_data', {}).get('account_balance')  # Include account balance info even for errors
            })

    if progress:
        progress(1, desc="Analysis Complete!")

    return all_results

import pandas as pd
import os
import time
import json

def generate_report_and_summary(analysis_results: list, exchange_name: str, limit: int, market_type: str = 'spot', account_balance_info: dict = None):
    """
    Generates a CSV report, JSON report, and a text summary from the analysis results.

    Args:
        analysis_results (list): The list of result dictionaries from run_full_analysis.
        exchange_name (str): The name of the primary exchange.
        limit (int): The number of symbols analyzed.
        market_type (str): The market type ('spot' or 'futures'). Defaults to 'spot'.
        account_balance_info (dict, optional): Account balance information retrieved from exchange.

    Returns:
        tuple: (summary_text, csv_filepath, json_filepath)
    """
    if not analysis_results or isinstance(analysis_results, dict) and "error" in analysis_results:
        summary = "Analysis did not yield any results or an error occurred."
        return summary, None, None

    # --- CSV Generation ---
    df = pd.DataFrame(analysis_results)

    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    csv_filename = f"report_{exchange_name}_{limit}_{market_type}_{timestamp}.csv"
    csv_filepath = os.path.join(report_dir, csv_filename)

    df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
    print(f"CSV Report saved to {csv_filepath}")

    # --- JSON Generation (for API integration) ---
    json_filename = f"report_{exchange_name}_{limit}_{market_type}_{timestamp}.json"
    json_filepath = os.path.join(report_dir, json_filename)

    # Format the results for JSON output that's suitable for API integration
    json_results = {
        "exchange": exchange_name,
        "market_type": market_type,
        "total_symbols_analyzed": limit,
        "successful_analyses": len(analysis_results),
        "timestamp": timestamp,
    }

    # Add account balance information if available
    if account_balance_info:
        json_results["account_balance"] = account_balance_info

    json_results["results"] = []

    for result in analysis_results:
        # Format for OKX API compatibility
        json_result = {
            "symbol": result.get("symbol"),
            "signal": result.get("signal"),
            "confidence": result.get("confidence"),
            "reasoning": result.get("reasoning"),
            "entry_price": result.get("entry_price"),
            "stop_loss": result.get("stop_loss"),
            "take_profit": result.get("take_profit"),
            "position_size": result.get("position_size", 0.02),  # Default to 2% of portfolio
            "market_type": result.get("market_type", market_type),  # Include market type
            "exchange_used": result.get("exchange", exchange_name)  # Include which exchange was used for this symbol
        }

        # Add OKX-specific format fields for futures trading if needed
        if result.get("signal") in ["Buy", "Long"]:
            json_result["action"] = "BUY"  # OKX API format
        elif result.get("signal") in ["Sell", "Short"]:
            json_result["action"] = "SELL"  # OKX API format
        else:
            json_result["action"] = "HOLD"

        # For futures, include leverage information
        if market_type == 'futures':
            json_result["leverage"] = result.get("leverage", DEFAULT_FUTURES_LEVERAGE)
            json_result["funding_rate"] = result.get("funding_rate_info", {})

        json_results["results"].append(json_result)

    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, ensure_ascii=False, indent=2)
    print(f"JSON Report saved to {json_filepath}")

    # --- Summary Generation ---
    # Now include information about which exchanges were used
    successful_exchanges = set()
    for result in analysis_results:
        exchange_used = result.get("exchange", exchange_name)
        successful_exchanges.add(exchange_used)

    exchanges_str = ", ".join(successful_exchanges) if successful_exchanges else exchange_name

    buy_signals = [r for r in analysis_results if r.get('signal') in ['BUY', 'STRONG_BUY', 'Buy', 'Long']]

    if not buy_signals:
        summary = (f"**Analysis Complete for {len(analysis_results)}/{limit} Symbols on {exchanges_str} ({market_type})**\n\n"
                   "No strong buy signals were identified at this time. "
                   "It is recommended to hold or wait for clearer market opportunities.\n\n"
                   f"A detailed report for all analyzed symbols is available for download.")
        return summary, csv_filepath, json_filepath

    # Sort recommended buys by confidence
    sorted_buys = sorted(buy_signals, key=lambda x: x.get('confidence', 0.0), reverse=True)

    summary = f"**Analysis Complete for {len(analysis_results)}/{limit} Symbols on {exchanges_str} ({market_type})**\n\n"
    summary += "### Top Investment Recommendations:\n\n"

    for item in sorted_buys:
        exchange_used = item.get("exchange", exchange_name)
        summary += (f"- **{item['symbol']}** (on {exchange_used})\n"
                    f"  - **Signal:** {item['signal']} (Confidence: {item.get('confidence', 'N/A'):.2f})\n"
                    f"  - **Reasoning:** {item.get('reasoning', 'No reasoning provided.')}\n")

    summary += f"\nA detailed report for all analyzed symbols has been generated and is available for download."

    return summary, csv_filepath, json_filepath

if __name__ == '__main__':
    # To run this file for production, analyze the symbols defined in config.py for both spot and futures markets
    import logging

    async def main():
        print("--- Running Batch Analyzer for Configured Symbols ---")
        print(f"Analyzing symbols from config.py: {CRYPTO_CURRENCIES_TO_ANALYZE}")

        # Analyze spot market with account balance
        print("\nAnalyzing SPOT market...")
        spot_results = await run_full_analysis(exchange_name="okx", market_type="spot", include_account_balance=True)

        if spot_results:
            print("\n--- Generating Report for SPOT Market ---")
            actual_analyzed_count = len(spot_results)
            # Get account balance info from first result if available, or retrieve separately
            account_balance_info = None
            if spot_results and spot_results[0] and 'account_balance' in spot_results[0]:
                account_balance_info = spot_results[0]['account_balance']
            spot_summary, spot_csv, spot_json = generate_report_and_summary(spot_results, "okx", actual_analyzed_count, market_type="spot", account_balance_info=account_balance_info)
            print(spot_summary)
        else:
            print("No results for SPOT market analysis.")

        print("\n" + "="*50 + "\n")

        # Analyze futures market with account balance
        print("Analyzing FUTURES market...")
        futures_results = await run_full_analysis(exchange_name="okx", market_type="futures", leverage=5, include_account_balance=True)

        if futures_results:
            print("\n--- Generating Report for FUTURES Market ---")
            actual_analyzed_count = len(futures_results)
            # Get account balance info from first result if available, or retrieve separately
            account_balance_info = None
            if futures_results and futures_results[0] and 'account_balance' in futures_results[0]:
                account_balance_info = futures_results[0]['account_balance']
            futures_summary, futures_csv, futures_json = generate_report_and_summary(futures_results, "okx", actual_analyzed_count, market_type="futures", account_balance_info=account_balance_info)
            print(futures_summary)
        else:
            print("No results for FUTURES market analysis.")

    asyncio.run(main())
