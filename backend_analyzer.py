"""
後台分析引擎 - 用於產生JSON格式的交易決策
支持後台運行，無需GUI界面，可以直接與交易系統整合
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, List

import pandas as pd

from chat_interface import CryptoAnalysisBot
from graph import app
from models import FinalApproval
from utils import safe_float
from okx_api_connector import OKXAPIConnector
from config import CRYPTO_CURRENCIES_TO_ANALYZE


class BackendAnalyzer:
    """後台分析引擎 - 產生JSON格式的交易決策"""

    def __init__(self):
        self.analysis_bot = CryptoAnalysisBot()

    def analyze_symbol(self, symbol: str, exchange: str = None, interval: str = "1d", limit: int = 100, include_account_balance: bool = True) -> Dict:
        """
        分析單個加密貨幣並返回JSON格式的決策

        Args:
            symbol: 加密貨幣符號 (如 BTC, BTCUSDT)
            exchange: 交易所名稱 (如 binance, okx)
            interval: K線週期 (如 1d, 4h, 1h)
            limit: K線數量限制
            include_account_balance: 是否包含帳戶餘額資訊 (僅適用於OKX)

        Returns:
            Dict: 包含現貨和合約交易決策的字典
        """
        print(f">> 開始後台分析: {symbol}")

        # 初始化帳戶餘額資訊
        account_balance_info = None

        # 如果是OKX交易所且需要帳戶餘額，則獲取帳戶資訊
        if include_account_balance and exchange and exchange.lower() == 'okx':
            try:
                okx_connector = OKXAPIConnector()
                # 獲取帳戶餘額 (以USDT為主)
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
            # 使用現有的分析方法獲取結果
            spot_result, futures_result, summary_gen = self.analysis_bot.analyze_crypto(
                symbol, exchange, interval, limit
            )

            # 生成JSON格式的交易決策
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

        # 基本信息
        output = {
            "symbol": symbol,
            "analysis_timestamp": datetime.now().isoformat(),
            "exchange": spot_result.get('exchange', 'unknown').upper() if spot_result else 'unknown',
            "current_price": safe_float(spot_result.get('current_price', 0)) if spot_result else 0,
            "spot_decision": self._extract_decision(spot_result, 'spot'),
            "futures_decision": self._extract_decision(futures_result, 'futures')
        }

        # 如果有帳戶餘額資訊，則加入到輸出中
        if account_balance_info:
            output["account_balance"] = account_balance_info

        return output

    def _extract_decision(self, result: Optional[Dict], market_type: str) -> Dict:
        """從分析結果中提取決策信息"""

        if not result:
            return {
                "should_trade": False,
                "decision": "Hold",
                "action": "hold",  # 兼容性字段
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": "No analysis result available",
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "leverage": 1 if market_type == "spot" else 10,  # 預設槓桿
                "risk_level": "未知",
                "market_type": market_type,
                "additional_params": {}
            }

        # 獲取最終批准結果
        final_approval = result.get('final_approval')
        trader_decision = result.get('trader_decision')

        if not final_approval:
            return {
                "should_trade": False,
                "decision": "Hold",
                "action": "hold",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": "No final approval available",
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "leverage": 1 if market_type == "spot" else 10,
                "risk_level": "未知",
                "market_type": market_type,
                "additional_params": {}
            }

        # 判斷是否應該交易 (批准狀態)
        should_trade = final_approval.final_decision in ["Approve", "Amended"]

        # 決策映射
        action_map = {
            "Buy": "buy", "Sell": "sell", "Hold": "hold",
            "Long": "long", "Short": "short"
        }
        decision_map = {
            "Buy": "買入", "Sell": "賣出", "Hold": "觀望",
            "Long": "做多", "Short": "做空"
        }

        # 提取交易決策
        trade_action = trader_decision.decision if trader_decision else "Hold"
        action = action_map.get(str(trade_action), "hold")
        decision = decision_map.get(str(trade_action), "觀望")

        # 提取相關參數
        position_size = safe_float(getattr(final_approval, 'final_position_size', 0))
        confidence = safe_float(getattr(trader_decision, 'confidence', 0)) if trader_decision else 0
        entry_price = safe_float(getattr(trader_decision, 'entry_price', None))
        stop_loss = safe_float(getattr(trader_decision, 'stop_loss', None))
        take_profit = safe_float(getattr(trader_decision, 'take_profit', None))

        # 獲取槓桿 (僅合約市場有效)
        leverage = getattr(final_approval, 'approved_leverage', 10) if market_type == "futures" else 1
        if not leverage:
            leverage = 10 if market_type == "futures" else 1

        # 風險評估信息
        risk_assessment = result.get('risk_assessment')
        risk_level = "未知"
        warnings = []
        adjustments = ""
        if risk_assessment:
            risk_level = getattr(risk_assessment, 'risk_level', '未知')
            warnings = getattr(risk_assessment, 'warnings', [])
            adjustments = getattr(risk_assessment, 'suggested_adjustments', '')

        # 技術指標信息
        tech_indicators = result.get('技術指標', {})
        market_structure = result.get('市場結構', {})

        # 價格信息
        price_info = result.get('價格資訊', {})

        # 辯論結果
        bull_argument = result.get('bull_argument')
        bear_argument = result.get('bear_argument')

        return {
            "should_trade": should_trade,
            "decision": decision,
            "action": action,
            "position_size": position_size,
            "confidence": confidence,
            "reasoning": getattr(final_approval, 'rationale', ''),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "leverage": leverage,
            "risk_level": risk_level,
            "market_type": market_type,
            "additional_params": {
                "risk_info": {
                    "risk_level": risk_level,
                    "warnings": warnings,
                    "adjustments": adjustments
                },
                "tech_indicators": tech_indicators,
                "market_structure": market_structure,
                "price_info": price_info,
                "bull_argument": {
                    "confidence": getattr(bull_argument, 'confidence', 0) if bull_argument else 0,
                    "argument": getattr(bull_argument, 'argument', '') if bull_argument else '',
                    "key_points": getattr(bull_argument, 'key_points', []) if bull_argument else []
                } if bull_argument else None,
                "bear_argument": {
                    "confidence": getattr(bear_argument, 'confidence', 0) if bear_argument else 0,
                    "argument": getattr(bear_argument, 'argument', '') if bear_argument else '',
                    "key_points": getattr(bear_argument, 'key_points', []) if bear_argument else []
                } if bear_argument else None,
                "funding_rate_info": result.get("funding_rate_info", {}),
                "news_info": result.get("新聞資訊", {})
            }
        }

    def _create_error_result(self, symbol: str, error_msg: str) -> Dict:
        """創建錯誤結果"""
        return {
            "symbol": symbol,
            "analysis_timestamp": datetime.now().isoformat(),
            "error": error_msg,
            "spot_decision": {
                "should_trade": False,
                "decision": "Error",
                "action": "error",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": error_msg,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "leverage": 1,
                "additional_params": {}
            },
            "futures_decision": {
                "should_trade": False,
                "decision": "Error",
                "action": "error",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": error_msg,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "leverage": 1,
                "additional_params": {}
            }
        }

    def analyze_multiple_symbols(self, symbols: List[str], exchange: str = None,
                                interval: str = "1d", limit: int = 100, include_account_balance: bool = True) -> List[Dict]:
        """批量分析多個加密貨幣"""
        results = []
        for symbol in symbols:
            result = self.analyze_symbol(symbol, exchange, interval, limit, include_account_balance)
            results.append(result)
        return results

    def save_decision_to_json(self, decision_data: Dict, filepath: str = None):
        """將決策結果保存為JSON文件"""
        if not filepath:
            # 生成預設文件名
            symbol = decision_data.get('symbol', 'unknown')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"trading_decisions_{symbol}_{timestamp}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(decision_data, f, ensure_ascii=False, indent=2)

        print(f">> 交易決策已保存至: {filepath}")
        return filepath

    def save_multiple_decisions_to_json(self, decisions_list: List[Dict], filepath: str = None):
        """將多個決策結果保存為JSON文件"""
        if not filepath:
            # 生成預設文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"trading_decisions_batch_{timestamp}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(decisions_list, f, ensure_ascii=False, indent=2)

        print(f">> 批量交易決策已保存至: {filepath}")
        return filepath


def run_backend_analysis(symbol: str, exchange: str = None, interval: str = "1d", limit: int = 100,
                        output_file: str = None, include_account_balance: bool = True):
    """
    執行後台分析的主要函數

    Args:
        symbol: 加密貨幣符號
        exchange: 交易所
        interval: K線週期
        limit: K線數量
        output_file: 輸出文件路徑
        include_account_balance: 是否包含帳戶餘額資訊 (僅適用於OKX)

    Returns:
        Dict: 分析結果
    """
    analyzer = BackendAnalyzer()

    # 執行分析
    result = analyzer.analyze_symbol(symbol, exchange, interval, limit, include_account_balance)

    # 保存結果
    if output_file:
        analyzer.save_decision_to_json(result, output_file)
    else:
        # 使用預設文件名
        analyzer.save_decision_to_json(result)

    return result


def run_batch_backend_analysis(symbols: List[str] = None, exchange: str = None,
                              interval: str = "1d", limit: int = 100,
                              output_file: str = None, include_account_balance: bool = True):
    """
    執行批量後台分析

    Args:
        symbols: 加密貨幣符號列表 (如果為 None，則使用 config 中設定的幣種)
        exchange: 交易所
        interval: K線週期
        limit: K線數量
        output_file: 輸出文件路徑
        include_account_balance: 是否包含帳戶餘額資訊 (僅適用於OKX)

    Returns:
        List[Dict]: 分析結果列表
    """
    analyzer = BackendAnalyzer()

    # 如果沒有提供符號列表，則使用配置文件中的幣種
    if symbols is None:
        symbols = CRYPTO_CURRENCIES_TO_ANALYZE

    # 執行批量分析 - 需要修改 analyze_multiple_symbols 方法以支持帳戶餘額
    results = []
    for symbol in symbols:
        result = analyzer.analyze_symbol(symbol, exchange, interval, limit, include_account_balance)
        results.append(result)

    # 保存結果
    if output_file:
        analyzer.save_multiple_decisions_to_json(results, output_file)
    else:
        # 使用預設文件名
        analyzer.save_multiple_decisions_to_json(results)

    return results


if __name__ == "__main__":
    # 測試後台分析功能
    print(">> 測試後台分析系統")
    print(f">> 使用配置文件中的幣種: {CRYPTO_CURRENCIES_TO_ANALYZE}")

    # 批量分析配置文件中的幣種
    results = run_batch_backend_analysis(
        exchange="okx",  # 使用OKX以支援帳戶餘額功能
        interval="1d",
        limit=100,
        include_account_balance=True  # 包含帳戶餘額資訊
    )

    print(f"\n>> 批量分析完成，共分析 {len(results)} 個幣種")

    for result in results:
        print(f"\n  - 幣種: {result['symbol']}")
        print(f"    現貨是否交易: {result['spot_decision']['should_trade']}")
        print(f"    現貨決策: {result['spot_decision']['decision']}")
        print(f"    合約是否交易: {result['futures_decision']['should_trade']}")
        print(f"    合約決策: {result['futures_decision']['decision']}")
        print(f"    現貨倉位大小: {result['spot_decision']['position_size']:.2%}")
        print(f"    合約倉位大小: {result['futures_decision']['position_size']:.2%}")

        # 顯示帳戶餘額資訊（如果存在）
        if 'account_balance' in result:
            print(f"    總餘額: {result['account_balance']['total_balance']} USDT")
            print(f"    可用餘額: {result['account_balance']['available_balance']} USDT")