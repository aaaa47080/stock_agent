"""
加密貨幣分析工具

This module now imports from the crypto_modules subpackage for better organization.
All tools are still available from this module for backward compatibility.
"""

from .crypto_modules import (
    explain_market_movement_tool,
    extract_crypto_symbols_tool,
    get_address_transactions,
    get_contract_info,
    get_crypto_categories_and_gainers,
    get_crypto_price_tool,
    get_current_time_taipei,
    # DeFi
    get_defillama_tvl,
    # DEX
    get_dex_pair_info,
    get_erc20_token_balance,
    # Etherscan
    get_eth_balance,
    get_eth_price_from_etherscan,
    get_exchange_flow,
    # Sentiment
    get_fear_and_greed_index,
    get_futures_data,
    # On-chain
    get_gas_fees,
    get_staking_yield,
    get_token_supply,
    get_token_unlocks,
    get_trending_dex_pairs,
    get_trending_tokens,
    get_whale_transactions,
    news_analysis_tool,
    search_dex_pairs,
    # Analysis
    technical_analysis_tool,
)

__all__ = [
    # Analysis
    "technical_analysis_tool",
    "news_analysis_tool",
    "get_crypto_price_tool",
    "explain_market_movement_tool",
    # Sentiment
    "get_fear_and_greed_index",
    "get_trending_tokens",
    "get_futures_data",
    "get_current_time_taipei",
    # DeFi
    "get_defillama_tvl",
    "get_crypto_categories_and_gainers",
    "get_token_unlocks",
    "get_token_supply",
    "extract_crypto_symbols_tool",
    "get_staking_yield",
    # On-chain
    "get_gas_fees",
    "get_whale_transactions",
    "get_exchange_flow",
    # Etherscan
    "get_eth_balance",
    "get_erc20_token_balance",
    "get_address_transactions",
    "get_contract_info",
    "get_eth_price_from_etherscan",
    # DEX
    "get_dex_pair_info",
    "get_trending_dex_pairs",
    "search_dex_pairs",
]
