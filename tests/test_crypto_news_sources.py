"""Tests for crypto news source selection defaults."""

from unittest.mock import patch

from utils.utils import get_crypto_news


def test_crypto_news_defaults_to_google_rss_only():
    """Default aggregation should only use the free RSS source."""
    with patch("utils.utils.get_crypto_news_google", return_value=[]):
        with patch("utils.utils.get_crypto_news_cryptocompare") as mock_compare:
            with patch("utils.utils.get_crypto_news_cryptopanic") as mock_panic:
                with patch("utils.utils.get_crypto_news_newsapi") as mock_newsapi:
                    get_crypto_news("BTC", limit=5)

    mock_compare.assert_not_called()
    mock_panic.assert_not_called()
    mock_newsapi.assert_not_called()


def test_crypto_news_filters_premium_sources_from_explicit_requests():
    """Explicit premium/API source requests should currently be ignored."""
    with patch("utils.utils.get_crypto_news_google", return_value=[]):
        with patch("utils.utils.get_crypto_news_cryptocompare") as mock_compare:
            with patch("utils.utils.get_crypto_news_cryptopanic") as mock_panic:
                with patch("utils.utils.get_crypto_news_newsapi") as mock_newsapi:
                    get_crypto_news(
                        "BTC",
                        limit=5,
                        enabled_sources=[
                            "google",
                            "cryptocompare",
                            "cryptopanic",
                            "newsapi",
                        ],
                    )

    mock_compare.assert_not_called()
    mock_panic.assert_not_called()
    mock_newsapi.assert_not_called()
