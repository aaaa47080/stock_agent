"""
Web Search Tool using DuckDuckGo (Free)
"""
import json
from typing import List, Dict, Optional
from langchain_core.tools import tool
from duckduckgo_search import DDGS
from api.utils import logger

def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict]:
    """
    Perform a web search using DuckDuckGo.
    
    Args:
        query: The search query.
        max_results: Maximum number of results to return.
        
    Returns:
        List of dictionaries containing 'title', 'href', and 'body'.
    """
    logger.info(f"🔎 performing web search for: {query}")
    try:
        results = []
        with DDGS() as ddgs:
            # DDGS.text() returns a generator of results
            # keywords: headers=None, region='wt-wt', safesearch='moderate', timelimit=None, backend='api'
            ddgs_gen = ddgs.text(query, max_results=max_results)
            for r in ddgs_gen:
                results.append({
                    "title": r.get('title', ''),
                    "link": r.get('href', ''),
                    "snippet": r.get('body', '')
                })
        
        logger.info(f"✅ Found {len(results)} results for: {query}")
        return results
    except Exception as e:
        logger.error(f"❌ Web search failed: {e}")
        return []

@tool
def web_search_tool(query: str, purpose: str = "general") -> str:
    """
    Perform a general web search to find information not available in the internal database.
    Use this for:
    1. Looking up current events, news, or market sentiment.
    2. Finding specific facts (e.g., "Pi Network current price", "competitors of Solana").
    3. Verifying information.
    
    Args:
        query: The search query string (e.g. "Bitcoin latest news", "Pi Network mainnet launch date").
        purpose: Brief explanation of why this search is being performed (for logging).
    """
    results = search_duckduckgo(query, max_results=5)
    
    if not results:
        return f"No results found for query: {query}"
    
    # Format results as a readable string
    output = f"### Search Results for '{query}'\n\n"
    for i, res in enumerate(results, 1):
        output += f"{i}. **{res['title']}**\n"
        output += f"   {res['snippet']}\n"
        output += f"   Source: {res['link']}\n\n"
        
    return output
