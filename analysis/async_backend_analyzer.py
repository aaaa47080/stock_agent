"""
非同步後台分析引擎 - 用於產生JSON格式的交易決策
支持非同步並行分析以提高速度，同時保持交易的順序安全性
"""
import argparse
import json
import os
import sys
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Optional, List

import pandas as pd

# Add the parent directory to the Python path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interfaces.chat_interface import CryptoAnalysisBot
from core.graph import app
from core.models import FinalApproval
from utils.utils import safe_float, DataFrameEncoder
from trading.okx_api_connector import OKXAPIConnector
from core.config import (
    CRYPTO_CURRENCIES_TO_ANALYZE,
    MINIMUM_INVESTMENT_USD,
    EXCHANGE_MINIMUM_ORDER_USD
)
from trading.okx_auto_trader import execute_trades_from_decision_data


class AsyncBackendAnalyzer:
    """非同步後台分析引擎 - 產生JSON格式的交易決策"""

    def __init__(self):
        self.analysis_bot = CryptoAnalysisBot()

    def analyze_symbol(self, symbol: str, exchange: str = None,
                     interval: str = "1d", limit: int = 100,
                     include_account_balance: bool = True,
                     short_term_interval: str = "1h",
                     medium_term_interval: str = "4h",
                     long_term_interval: str = "1d") -> Dict:
        """
        分析單個加密貨幣並返回JSON格式的決策
        """
        print(f">> 開始後台分析: {symbol}")
        print(f">> 使用時間週期: 短期({short_term_interval}), 中期({medium_term_interval}), 長期({long_term_interval})")

        account_balance_info = None
        if include_account_balance and exchange and exchange.lower() == 'okx':
            try:
                okx_connector = OKXAPIConnector()
                balance_response = okx_connector.get_account_balance("USDT")
                if balance_response.get("code") == "0":
                    balance_data = balance_response.get("data", [])
                    if balance_data:
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
                            print(f">> 帳戶餘額資訊: 總餘額=${total_balance}, 可用餘額=${available_balance}")
            except Exception as e:
                print(f">> 獲取帳戶餘額時發生錯誤: {str(e)}")
                account_balance_info = None

        try:
            if account_balance_info and account_balance_info.get('available_balance', 0) < MINIMUM_INVESTMENT_USD:
                 print(f">> 可用餘額低於 ${MINIMUM_INVESTMENT_USD}，將不會觸發交易。")
                 # We still run the analysis, but trading will be disabled in _extract_decision
                 pass

            spot_result, futures_result, summary_gen = self.analysis_bot.analyze_crypto(
                symbol, exchange, interval, limit,
                account_balance_info=account_balance_info,
                short_term_interval=short_term_interval,
                medium_term_interval=medium_term_interval,
                long_term_interval=long_term_interval
            )

            result = self._format_decision_output(
                symbol, spot_result, futures_result, summary_gen, account_balance_info
            )

            print(f">> {symbol} 後台分析完成")
            return result

        except Exception as e:
            print(f">> 分析 {symbol} 時發生錯誤: {str(e)}")
            return self._create_error_result(symbol, str(e))

    def _format_decision_output(
        self,
        symbol: str,
        spot_result: Optional[Dict],
        futures_result: Optional[Dict],
        summary_gen,
        account_balance_info: Optional[Dict] = None
    ) -> Dict:
        """將分析結果格式化為JSON輸出"""
        output = {
            "symbol": symbol,
            "analysis_timestamp": datetime.now().isoformat(),
            "exchange": spot_result.get('exchange', 'unknown').upper() if spot_result else 'unknown',
            "current_price": safe_float(spot_result.get('current_price', 0)) if spot_result else 0,
            "spot_decision": self._extract_decision(symbol, spot_result, 'spot', account_balance_info),
            "futures_decision": self._extract_decision(symbol, futures_result, 'futures', account_balance_info)
        }
        if account_balance_info:
            output["account_balance"] = account_balance_info
        return output

    def _extract_decision(self, symbol: str, result: Optional[Dict], market_type: str, account_balance_info: Optional[Dict] = None) -> Dict:
        """從分析結果中提取決策信息"""
        # Convert symbol from Binance format (e.g. "PIUSDT") to OKX format (e.g. "PI-USDT")
        # First remove any existing USDT/BUSD suffix and then add the correct format
        # Handle both "PIUSDT" and "PI-USDT" formats correctly
        upper_symbol = symbol.upper()

        # Check if symbol already contains OKX format (with hyphens)
        if '-' in upper_symbol:
            # If it's already in OKX format like "PI-USDT", extract base symbol correctly
            parts = upper_symbol.split('-')
            if len(parts) >= 2 and parts[-1] in ['USDT', 'BUSD']:
                base_symbol = parts[0]  # Take the first part (PI)
            else:
                base_symbol = parts[0]  # For formats like "PI-USDT-SWAP" take first part
        elif upper_symbol.endswith('USDT'):
            # Handle Binance format like "PIUSDT"
            base_symbol = upper_symbol[:-4]  # Remove 'USDT' from end
        elif upper_symbol.endswith('BUSD'):
            # Handle BUSD format
            base_symbol = upper_symbol[:-4]  # Remove 'BUSD' from end
        else:
            # Unknown format, just use as-is
            base_symbol = upper_symbol

        trade_symbol = f"{base_symbol}-USDT"
        if market_type == 'futures':
            trade_symbol += "-SWAP"

        base_decision = {
            "should_trade": False, "decision": "Hold", "action": "hold", "symbol_for_trade": trade_symbol,
            "position_size_percentage": 0.0, "investment_amount_usdt": 0.0, "confidence": 0.0,
            "reasoning": "No analysis result available", "entry_price": None, "stop_loss": None,
            "take_profit": None, "leverage": 1 if market_type == "spot" else 10,
            "risk_level": "未知", "market_type": market_type, "additional_params": {}
        }

        if not result: return base_decision

        final_approval = result.get('final_approval')
        trader_decision = result.get('trader_decision')

        if not final_approval or not trader_decision:
            base_decision["reasoning"] = "No final approval or trader decision available"
            return base_decision

        should_trade = final_approval.final_decision in ["Approve", "Amended"]
        reasoning = getattr(final_approval, 'rationale', '')

        if should_trade and account_balance_info:
            available_balance = account_balance_info.get('available_balance', 0.0)
            if available_balance < MINIMUM_INVESTMENT_USD:
                should_trade = False
                reasoning = f"交易決策被覆蓋：可用餘額 ${available_balance:.2f} 低於最低投資要求 ${MINIMUM_INVESTMENT_USD:.2f}。"

        action_map = {"Buy": "buy", "Sell": "sell", "Hold": "hold", "Long": "long", "Short": "short"}
        decision_map = {"Buy": "買入", "Sell": "賣出", "Hold": "觀望", "Long": "做多", "Short": "做空"}

        trade_action = trader_decision.decision
        action = action_map.get(str(trade_action), "hold")
        decision = decision_map.get(str(trade_action), "觀望")

        position_size = safe_float(getattr(final_approval, 'final_position_size', 0))
        confidence = safe_float(getattr(trader_decision, 'confidence', 0))
        entry_price = safe_float(getattr(trader_decision, 'entry_price', None))
        stop_loss = safe_float(getattr(trader_decision, 'stop_loss', None))
        take_profit = safe_float(getattr(trader_decision, 'take_profit', None))
        leverage = getattr(final_approval, 'approved_leverage', 10) if market_type == "futures" else 1

        investment_amount = 0.0
        if account_balance_info and should_trade:
            available_balance = account_balance_info.get('available_balance', 0.0)
            investment_amount = available_balance * position_size
            if investment_amount < EXCHANGE_MINIMUM_ORDER_USD:
                should_trade = False
                reasoning = f"交易決策被覆蓋：計算出的投資金額 ${investment_amount:.2f} 低於交易所最低要求 ${EXCHANGE_MINIMUM_ORDER_USD:.2f}。"

        risk_assessment = result.get('risk_assessment')
        risk_level = getattr(risk_assessment, 'risk_level', '未知') if risk_assessment else "未知"
        warnings = getattr(risk_assessment, 'warnings', []) if risk_assessment else []
        adjustments = getattr(risk_assessment, 'suggested_adjustments', '') if risk_assessment else ""

        return {
            "should_trade": should_trade, "decision": decision, "action": action, "symbol_for_trade": trade_symbol,
            "position_size_percentage": position_size, "investment_amount_usdt": investment_amount, "confidence": confidence,
            "reasoning": reasoning, "entry_price": entry_price, "stop_loss": stop_loss,
            "take_profit": take_profit, "leverage": leverage or (10 if market_type == "futures" else 1),
            "risk_level": risk_level, "market_type": market_type,
            "additional_params": {
                "risk_info": {"risk_level": risk_level, "warnings": warnings, "adjustments": adjustments},
                "tech_indicators": result.get('技術指標', {}), "market_structure": result.get('市場結構', {}),
                "price_info": result.get('價格資訊', {}),
                "bull_argument": {
                    "confidence": getattr(result.get('bull_argument'), 'confidence', 0), "argument": getattr(result.get('bull_argument'), 'argument', ''),
                    "key_points": getattr(result.get('bull_argument'), 'key_points', [])
                } if result.get('bull_argument') else None,
                "bear_argument": {
                    "confidence": getattr(result.get('bear_argument'), 'confidence', 0), "argument": getattr(result.get('bear_argument'), 'argument', ''),
                    "key_points": getattr(result.get('bear_argument'), 'key_points', [])
                } if result.get('bear_argument') else None,
                "funding_rate_info": result.get("funding_rate_info", {}), "news_info": result.get("新聞資訊", {})
            }
        }

    def _create_error_result(self, symbol: str, error_msg: str) -> Dict:
        return {
            "symbol": symbol, "analysis_timestamp": datetime.now().isoformat(), "error": error_msg,
            "spot_decision": {"should_trade": False, "decision": "Error", "action": "error", "position_size": 0.0, "confidence": 0.0, "reasoning": error_msg, "entry_price": None, "stop_loss": None, "take_profit": None, "leverage": 1, "additional_params": {}},
            "futures_decision": {"should_trade": False, "decision": "Error", "action": "error", "position_size": 0.0, "confidence": 0.0, "reasoning": error_msg, "entry_price": None, "stop_loss": None, "take_profit": None, "leverage": 1, "additional_params": {}}
        }

    def save_decision_to_json(self, decision_data: Dict, filepath: str = None):
        if not filepath:
            symbol = decision_data.get('symbol', 'unknown')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"trading_decisions_{symbol}_{timestamp}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(decision_data, f, ensure_ascii=False, indent=2, cls=DataFrameEncoder)
        print(f">> 交易決策已保存至: {filepath}")
        return filepath

    def save_multiple_decisions_to_json(self, decisions_list: List[Dict], filepath: str = None):
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"trading_decisions_batch_{timestamp}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(decisions_list, f, ensure_ascii=False, indent=2, cls=DataFrameEncoder)
        print(f">> 批量交易決策已保存至: {filepath}")
        return filepath


# 使用線程鎖確保交易順序安全
trade_lock = threading.Lock()


async def run_async_batch_backend_analysis(symbols: List[str] = None, exchange: str = None,
                                          interval: str = "1d", limit: int = 100,
                                          output_file: str = None, include_account_balance: bool = True, auto_trade: bool = False,
                                          short_term="1h", medium_term="4h", long_term="1d"):
    """
    非同步批次分析 - 可並行分析多個代幣以提高速度，同時保持交易的順序安全性
    """
    analyzer = AsyncBackendAnalyzer()
    if symbols is None:
        symbols = CRYPTO_CURRENCIES_TO_ANALYZE
    
    async def analyze_single_symbol(symbol_index_tuple):
        idx, symbol = symbol_index_tuple
        print(f"\n----- Analyzing {symbol} ({idx + 1}/{len(symbols)}) -----")
        result = analyzer.analyze_symbol(
            symbol, exchange, interval, limit, include_account_balance,
            short_term_interval=short_term, medium_term_interval=medium_term, long_term_interval=long_term
        )
        
        # 進行交易時使用鎖確保順序安全
        if auto_trade:
            with trade_lock:
                print(f"\n[AUTO-TRADE] Attempting to execute trade for {symbol}...")
                execute_trades_from_decision_data([result], live_trading=True)
                print("-" * 20)
        
        return result
    
    # 使用 asyncio.gather 並行執行所有分析任務
    indexed_symbols = [(i, symbol) for i, symbol in enumerate(symbols)]
    tasks = [analyze_single_symbol(symbol_tuple) for symbol_tuple in indexed_symbols]
    all_results = await asyncio.gather(*tasks)
    
    # 保存所有結果到檔案
    filepath = analyzer.save_multiple_decisions_to_json(all_results, output_file)
    print(f"\nAsync batch analysis for {len(all_results)} symbols saved to {filepath}")
    
    return all_results


def run_backend_analysis(symbol: str, exchange: str = None, interval: str = "1d", limit: int = 100,
                        output_file: str = None, include_account_balance: bool = True, auto_trade: bool = False,
                        short_term="1h", medium_term="4h", long_term="1d"):
    analyzer = AsyncBackendAnalyzer()
    result = analyzer.analyze_symbol(
        symbol, exchange, interval, limit, include_account_balance,
        short_term_interval=short_term, medium_term_interval=medium_term, long_term_interval=long_term
    )
    filepath = analyzer.save_decision_to_json(result, output_file)
    print(f"Analysis saved to {filepath}")
    if auto_trade:
        print("\n[AUTO-TRADE] Initiating automated trading for single symbol...")
        execute_trades_from_decision_data([result], live_trading=True)
    return result


def run_sync_batch_backend_analysis(symbols: List[str] = None, exchange: str = None,
                                   interval: str = "1d", limit: int = 100,
                                   output_file: str = None, include_account_balance: bool = True, auto_trade: bool = False,
                                   short_term="1h", medium_term="4h", long_term="1d"):
    """
    同步批次分析 - 保持原有的順序執行方式
    """
    analyzer = AsyncBackendAnalyzer()
    if symbols is None:
        symbols = CRYPTO_CURRENCIES_TO_ANALYZE

    all_results = []
    for symbol in symbols:
        print(f"\n----- Analyzing {symbol} ({symbols.index(symbol) + 1}/{len(symbols)}) -----")
        result = analyzer.analyze_symbol(
            symbol, exchange, interval, limit, include_account_balance,
            short_term, medium_term, long_term
        )
        all_results.append(result)

        # Trade immediately after each analysis to use the most recent balance
        if auto_trade:
            print(f"\n[AUTO-TRADE] Attempting to execute trade for {symbol}...")
            execute_trades_from_decision_data([result], live_trading=True)
            print("-" * 20)

    # Save all results to a single file at the end
    filepath = analyzer.save_multiple_decisions_to_json(all_results, output_file)
    print(f"\nSync batch analysis for {len(all_results)} symbols saved to {filepath}")

    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async Backend Crypto Analysis Engine")
    parser.add_argument("--symbol", type=str, help="A single crypto symbol to analyze (e.g., BTC).")
    parser.add_argument("--batch", action="store_true", help="Run batch analysis on all symbols from the config file.")
    parser.add_argument("--async-batch", action="store_true", help="Run async batch analysis on all symbols (parallel analysis).")
    parser.add_argument("--exchange", type=str, default="okx", help="The exchange to use (e.g., okx).")
    parser.add_argument(
        "--interval", type=str, default="1h,4h,1d",
        help="Comma-separated list of intervals for short, medium, and long term analysis (e.g., '5m,15m,1h'). The last one is the main interval."
    )
    parser.add_argument("--auto-trade", action="store_true", help="Enable live auto-trading after analysis.")
    args = parser.parse_args()

    if not args.symbol and not args.batch and not args.async_batch:
        parser.error("You must specify either --symbol, --batch, or --async-batch.")

    intervals = [i.strip() for i in args.interval.split(',')]
    if len(intervals) == 0:
        intervals = ["1h", "4h", "1d"]

    short = intervals[0]
    medium = intervals[1] if len(intervals) > 1 else short
    long = intervals[2] if len(intervals) > 2 else medium
    main_interval = intervals[-1]

    if args.symbol:
        run_backend_analysis(
            symbol=args.symbol, exchange=args.exchange, interval=main_interval,
            include_account_balance=True, auto_trade=args.auto_trade,
            short_term=short, medium_term=medium, long_term=long
        )

    if args.batch:
        run_sync_batch_backend_analysis(
            exchange=args.exchange, interval=main_interval,
            include_account_balance=True, auto_trade=args.auto_trade,
            short_term=short, medium_term=medium, long_term=long
        )

    if args.async_batch:
        # 使用 asyncio.run 執行非同步批次分析
        asyncio.run(run_async_batch_backend_analysis(
            exchange=args.exchange, interval=main_interval,
            include_account_balance=True, auto_trade=args.auto_trade,
            short_term=short, medium_term=medium, long_term=long
        ))