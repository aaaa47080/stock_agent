"""
後台分析引擎 - 用於產生JSON格式的交易決策
支持後台運行，無需GUI界面，可以直接與交易系統整合
"""
import argparse
import json
import os
import sys
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
from core.config import CRYPTO_CURRENCIES_TO_ANALYZE
from trading.okx_auto_trader import execute_trades_from_decision_data


MINIMUM_INVESTMENT_USD = 100.0

class BackendAnalyzer:
    """後台分析引擎 - 產生JSON格式的交易決策"""

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

        # 初始化帳戶餘額資訊
        account_balance_info = None

        # 如果是OKX交易所且需要帳戶餘額，則獲取帳戶資訊
        if include_account_balance and exchange and exchange.lower() == 'okx':
            try:
                okx_connector = OKXAPIConnector()
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
                            print(f">> 帳戶餘額資訊: 總餘額=${total_balance}, 可用餘額=${available_balance}")
            except Exception as e:
                print(f">> 獲取帳戶餘額時發生錯誤: {str(e)}")
                account_balance_info = None

        try:
            # 如果餘額不足，則直接跳過分析，但仍返回結構
            if account_balance_info and account_balance_info.get('available_balance', 0) < MINIMUM_INVESTMENT_USD:
                 print(f">> 可用餘額低於 ${MINIMUM_INVESTMENT_USD}，跳過交易分析，僅提供市場觀察。")
                 # We can still run analysis but ensure trading is disabled.
                 # For now, we will just disable trading. The user can decide if they want to skip analysis entirely.
                 pass # Continue to analysis but the trading will be disabled in _extract_decision

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

        # Balance Check
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
            if investment_amount < 1: # OKX has minimum order size of 1 USD
                should_trade = False
                reasoning = f"交易決策被覆蓋：計算出的投資金額 ${investment_amount:.2f} 低於交易所最低要求。"

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

    def analyze_multiple_symbols(self, symbols: List[str], exchange: str = None,
                                interval: str = "1d", limit: int = 100, include_account_balance: bool = True,
                                short_term_interval: str = "1h", medium_term_interval: str = "4h", long_term_interval: str = "1d") -> List[Dict]:
        results = []
        for symbol in symbols:
            result = self.analyze_symbol(
                symbol, exchange, interval, limit, include_account_balance,
                short_term_interval, medium_term_interval, long_term_interval
            )
            results.append(result)
        return results

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


def run_backend_analysis(symbol: str, exchange: str = None, interval: str = "1d", limit: int = 100,
                        output_file: str = None, include_account_balance: bool = True, auto_trade: bool = False,
                        short_term="1h", medium_term="4h", long_term="1d"):
    analyzer = BackendAnalyzer()
    result = analyzer.analyze_symbol(
        symbol, exchange, interval, limit, include_account_balance,
        short_term_interval=short_term, medium_term_interval=medium_term, long_term_interval=long_term
    )
    filepath = analyzer.save_decision_to_json(result, output_file)
    print(f"Analysis saved to {filepath}")
    if auto_trade:
        print("\n[AUTO-TRADE] Initiating automated trading...")
        execute_trades_from_decision_data([result], live_trading=True)
    return result


def run_batch_backend_analysis(symbols: List[str] = None, exchange: str = None,
                              interval: str = "1d", limit: int = 100,
                              output_file: str = None, include_account_balance: bool = True, auto_trade: bool = False,
                              short_term="1h", medium_term="4h", long_term="1d"):
    analyzer = BackendAnalyzer()
    if symbols is None:
        symbols = CRYPTO_CURRENCIES_TO_ANALYZE
    results = analyzer.analyze_multiple_symbols(
        symbols, exchange, interval, limit, include_account_balance,
        short_term_interval=short_term, medium_term_interval=medium_term, long_term_interval=long_term
    )
    filepath = analyzer.save_multiple_decisions_to_json(results, output_file)
    print(f"Batch analysis saved to {filepath}")
    if auto_trade:
        print("\n[AUTO-TRADE] Initiating automated trading for batch...")
        execute_trades_from_decision_data(results, live_trading=True)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backend Crypto Analysis Engine")
    parser.add_argument("--symbol", type=str, help="A single crypto symbol to analyze (e.g., BTC).")
    parser.add_argument("--batch", action="store_true", help="Run batch analysis on all symbols from the config file.")
    parser.add_argument("--exchange", type=str, default="okx", help="The exchange to use (e.g., okx).")
    parser.add_argument(
        "--interval", type=str, default="1h,4h,1d",
        help="Comma-separated list of intervals for short, medium, and long term analysis (e.g., '5m,15m,1h'). The last one is the main interval."
    )
    parser.add_argument("--auto-trade", action="store_true", help="Enable live auto-trading after analysis.")
    args = parser.parse_args()

    if not args.symbol and not args.batch:
        parser.error("You must specify either --symbol or --batch.")

    intervals = [i.strip() for i in args.interval.split(',')]
    if len(intervals) == 0:
        intervals = ["1h", "4h", "1d"] # Default
        
    short = intervals[0]
    medium = intervals[1] if len(intervals) > 1 else short
    long = intervals[2] if len(intervals) > 2 else medium
    main_interval = intervals[-1] # The longest interval is used for the main data fetch

    if args.symbol:
        run_backend_analysis(
            symbol=args.symbol, exchange=args.exchange, interval=main_interval,
            include_account_balance=True, auto_trade=args.auto_trade,
            short_term=short, medium_term=medium, long_term=long
        )
    
    if args.batch:
        run_batch_backend_analysis(
            exchange=args.exchange, interval=main_interval,
            include_account_balance=True, auto_trade=args.auto_trade,
            short_term=short, medium_term=medium, long_term=long
        )

    def _create_error_result(self, symbol: str, error_msg: str) -> Dict:
        return {
            "symbol": symbol, "analysis_timestamp": datetime.now().isoformat(), "error": error_msg,
            "spot_decision": {"should_trade": False, "decision": "Error", "action": "error", "position_size": 0.0, "confidence": 0.0, "reasoning": error_msg, "entry_price": None, "stop_loss": None, "take_profit": None, "leverage": 1, "additional_params": {}},
            "futures_decision": {"should_trade": False, "decision": "Error", "action": "error", "position_size": 0.0, "confidence": 0.0, "reasoning": error_msg, "entry_price": None, "stop_loss": None, "take_profit": None, "leverage": 1, "additional_params": {}}
        }

    def analyze_multiple_symbols(self, symbols: List[str], exchange: str = None,
                                interval: str = "1d", limit: int = 100, include_account_balance: bool = True,
                                short_term_interval: str = "1h", medium_term_interval: str = "4h", long_term_interval: str = "1d") -> List[Dict]:
        results = []
        for symbol in symbols:
            result = self.analyze_symbol(
                symbol, exchange, interval, limit, include_account_balance,
                short_term_interval, medium_term_interval, long_term_interval
            )
            results.append(result)
        return results

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


def run_backend_analysis(symbol: str, exchange: str = None, interval: str = "1d", limit: int = 100,
                        output_file: str = None, include_account_balance: bool = True, auto_trade: bool = False,
                        short_term="1h", medium_term="4h", long_term="1d"):
    analyzer = BackendAnalyzer()
    result = analyzer.analyze_symbol(
        symbol, exchange, interval, limit, include_account_balance,
        short_term_interval=short_term, medium_term_interval=medium_term, long_term_interval=long_term
    )
    filepath = analyzer.save_decision_to_json(result, output_file)
    print(f"Analysis saved to {filepath}")
    if auto_trade:
        print("\n[AUTO-TRADE] Initiating automated trading...")
        execute_trades_from_decision_data([result], live_trading=True)
    return result


def run_batch_backend_analysis(symbols: List[str] = None, exchange: str = None,
                              interval: str = "1d", limit: int = 100,
                              output_file: str = None, include_account_balance: bool = True, auto_trade: bool = False,
                              short_term="1h", medium_term="4h", long_term="1d"):
    analyzer = BackendAnalyzer()
    if symbols is None:
        symbols = CRYPTO_CURRENCIES_TO_ANALYZE
    results = analyzer.analyze_multiple_symbols(
        symbols, exchange, interval, limit, include_account_balance,
        short_term_interval=short_term, medium_term_interval=medium_term, long_term_interval=long_term
    )
    filepath = analyzer.save_multiple_decisions_to_json(results, output_file)
    print(f"Batch analysis saved to {filepath}")
    if auto_trade:
        print("\n[AUTO-TRADE] Initiating automated trading for batch...")
        execute_trades_from_decision_data(results, live_trading=True)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backend Crypto Analysis Engine")
    parser.add_argument("--symbol", type=str, help="A single crypto symbol to analyze (e.g., BTC).")
    parser.add_argument("--batch", action="store_true", help="Run batch analysis on all symbols from the config file.")
    parser.add_argument("--exchange", type=str, default="okx", help="The exchange to use (e.g., okx).")
    parser.add_argument(
        "--interval", type=str, default="1h,4h,1d",
        help="Comma-separated list of intervals for short, medium, and long term analysis (e.g., '5m,15m,1h'). The last one is the main interval."
    )
    parser.add_argument("--auto-trade", action="store_true", help="Enable live auto-trading after analysis.")
    args = parser.parse_args()

    if not args.symbol and not args.batch:
        parser.error("You must specify either --symbol or --batch.")

    intervals = [i.strip() for i in args.interval.split(',')]
    if len(intervals) == 0:
        intervals = ["1h", "4h", "1d"] # Default
        
    short = intervals[0]
    medium = intervals[1] if len(intervals) > 1 else short
    long = intervals[2] if len(intervals) > 2 else medium
    main_interval = intervals[-1] # The longest interval is used for the main data fetch

    if args.symbol:
        run_backend_analysis(
            symbol=args.symbol, exchange=args.exchange, interval=main_interval,
            include_account_balance=True, auto_trade=args.auto_trade,
            short_term=short, medium_term=medium, long_term=long
        )
    
    if args.batch:
        run_batch_backend_analysis(
            exchange=args.exchange, interval=main_interval,
            include_account_balance=True, auto_trade=args.auto_trade,
            short_term=short, medium_term=medium, long_term=long
        )