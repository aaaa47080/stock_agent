"""
Generic LLM deep analysis helper — shared by commodity, forex, usstock, twstock pulse endpoints.
"""

from api.utils import logger, run_sync


async def deep_analyze_generic(
    symbol: str, context: str, llm_key: str, llm_provider: str
) -> str | None:
    """
    Call the user's LLM with market context to generate an AI analysis summary.
    Returns the AI-generated text, or None on failure.
    """
    try:
        from langchain_core.messages import HumanMessage

        from utils.llm_client import create_llm_client_from_config

        client, _ = create_llm_client_from_config(
            {
                "provider": llm_provider,
                "api_key": llm_key,
            }
        )

        prompt = (
            f"你是一位專業金融分析師。請根據以下市場數據，用繁體中文撰寫一段簡潔的市場脈動分析（3-4句話），"
            f"涵蓋：當前趨勢、技術面信號、以及短線展望。請直接給出分析文字，不要加任何標題或說明。\n\n"
            f"市場數據：\n{context}"
        )

        response = await run_sync(lambda: client.invoke([HumanMessage(content=prompt)]))
        text = response.content if hasattr(response, "content") else str(response)
        return text.strip()
    except Exception as e:
        logger.error(f"[deep_analyze_generic] {symbol} failed: {e}")
        return None
