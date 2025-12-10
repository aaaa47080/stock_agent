import asyncio
from tqdm import tqdm
import pandas as pd
import os
import time

# Import project-specific modules
from data_fetcher import get_data_fetcher, SymbolNotFoundError
from indicator_calculator import add_technical_indicators
from graph import app, AgentState
import config
from models import TraderDecision

async def run_full_analysis(exchange_name: str, limit: int = 30, progress=None):
    """
    Runs a full analysis on the top N symbols from a given exchange.

    Args:
        exchange_name (str): The name of the exchange ('Binance' or 'OKX').
        limit (int): The number of top symbols to analyze.
        progress (gradio.Progress): Gradio progress tracker.

    Returns:
        list: A list of dictionaries, where each dictionary is the analysis result for a symbol.
    """
    if progress:
        progress(0, desc="Initializing...")

    try:
        fetcher = get_data_fetcher(exchange_name)
    except ValueError as e:
        print(f"Error initializing: {e}")
        return {"error": str(e)}

    # 1. Get top symbols
    if progress:
        progress(0.05, desc=f"Fetching top {limit} symbols from {exchange_name}...")
    
    try:
        top_symbols = fetcher.get_top_symbols(limit=limit)
        if not top_symbols:
            print("No symbols found.")
            return {"error": "Could not fetch top symbols."}
    except Exception as e:
        print(f"Failed to get top symbols: {e}")
        return {"error": f"Failed to get top symbols: {e}"}

    # 2. Iterate and analyze each symbol
    all_results = []
    total_symbols = len(top_symbols)
    
    # Using tqdm for console progress, which will be tracked by Gradio's progress object
    for i, symbol in enumerate(tqdm(top_symbols, desc="Analyzing Symbols")):
        start_progress = 0.1
        end_progress = 0.9
        current_progress = start_progress + (i / total_symbols) * (end_progress - start_progress)
        
        if progress:
            progress(current_progress, desc=f"Analyzing {symbol} ({i+1}/{total_symbols})")

        try:
            # Fetch data for the symbol
            df = fetcher.get_historical_klines(symbol, config.ANALYSIS_INTERVAL, limit=config.KLINE_LIMIT)
            if df is None or df.empty:
                print(f"Skipping {symbol}: No K-line data returned.")
                continue
            
            # Process data and calculate indicators
            processed_df = add_technical_indicators(df)
            
            # Prepare initial state for the graph
            initial_state = AgentState(
                symbol=symbol,
                exchange=exchange_name,
                interval=config.ANALYSIS_INTERVAL,
                preloaded_data={
                    "kline_data": processed_df,
                    "news_data": None, # Batch mode doesn't include news for now
                    "funding_rate": None
                },
                final_decision=None,
                messages=[]
            )

            # Invoke the analysis graph
            # The graph is synchronous, but we run it in a way that doesn't block the UI event loop
            # by using asyncio.to_thread if this function was async. Since Gradio handles this, direct call is fine.
            final_state = app.invoke(initial_state, {"recursion_limit": 15})

            # Extract result
            if final_state and final_state.get('final_decision'):
                decision : TraderDecision = final_state['final_decision']
                result = {
                    "symbol": symbol,
                    "signal": decision.decision,
                    "confidence": decision.confidence,
                    "entry_price": decision.entry_price,
                    "stop_loss": decision.stop_loss,
                    "take_profit": decision.take_profit,
                    "reasoning": decision.reasoning
                }
                all_results.append(result)
            else:
                 all_results.append({
                    "symbol": symbol,
                    "signal": "ERROR",
                    "reasoning": "Analysis did not produce a final decision.",
                })


        except SymbolNotFoundError as e:
            print(f"Could not analyze {symbol}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while analyzing {symbol}: {e}")
            # Optionally, add error information to the results
            all_results.append({
                "symbol": symbol,
                "signal": "ERROR",
                "reasoning": str(e),
            })

    if progress:
        progress(1, desc="Analysis Complete!")
        
    return all_results

def generate_report_and_summary(analysis_results: list, exchange_name: str, limit: int):
    """
    Generates a CSV report and a text summary from the analysis results.

    Args:
        analysis_results (list): The list of result dictionaries from run_full_analysis.
        exchange_name (str): The name of the exchange.
        limit (int): The number of symbols analyzed.

    Returns:
        tuple: (summary_text, csv_filepath)
    """
    if not analysis_results or isinstance(analysis_results, dict) and "error" in analysis_results:
        summary = "Analysis did not yield any results or an error occurred."
        return summary, None

    # --- CSV Generation ---
    df = pd.DataFrame(analysis_results)
    
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    csv_filename = f"report_{exchange_name}_{limit}_{timestamp}.csv"
    csv_filepath = os.path.join(report_dir, csv_filename)
    
    df.to_csv(csv_filepath, index=False, encoding='utf-8-sig')
    print(f"Report saved to {csv_filepath}")

    # --- Summary Generation ---
    buy_signals = [r for r in analysis_results if r.get('signal') in ['BUY', 'STRONG_BUY', 'Buy', 'Long']]
    
    if not buy_signals:
        summary = (f"**Analysis Complete for {len(analysis_results)}/{limit} Symbols on {exchange_name}**\n\n"
                   "No strong buy signals were identified at this time. "
                   "It is recommended to hold or wait for clearer market opportunities.\n\n"
                   f"A detailed report for all analyzed symbols is available for download.")
        return summary, csv_filepath

    # Sort recommended buys by confidence
    sorted_buys = sorted(buy_signals, key=lambda x: x.get('confidence', 0.0), reverse=True)

    summary = f"**Analysis Complete for {len(analysis_results)}/{limit} Symbols on {exchange_name}**\n\n"
    summary += "### Top Investment Recommendations:\n\n"
    
    for item in sorted_buys:
        summary += (f"- **{item['symbol']}**\n"
                    f"  - **Signal:** {item['signal']} (Confidence: {item.get('confidence', 'N/A'):.2f})\n"
                    f"  - **Reasoning:** {item.get('reasoning', 'No reasoning provided.')}\n")
    
    summary += f"\nA detailed report for all analyzed symbols has been generated and is available for download."
    
    return summary, csv_filepath

if __name__ == '__main__':
    # To run this file for testing, you might need to adjust path if run from outside stock_agent
    # Example: python -m stock_agent.batch_analyzer
    import logging
    
    async def main():
        print("--- Running Batch Analyzer Test ---")
        # Using a small limit for testing
        results = await run_full_analysis(exchange_name="Binance", limit=5)
        
        if results:
            print("\n--- Generating Report and Summary ---")
            summary, csv_file = generate_report_and_summary(results, "Binance", 5)
            
            print("\n--- Summary ---")
            print(summary)
            
            if csv_file:
                print(f"\n--- CSV Report ---")
                print(f"Report available at: {csv_file}")
                # Print contents for verification
                print(pd.read_csv(csv_file).head())
        else:
            print("Analysis returned no results.")

    asyncio.run(main())
