import pytest


@pytest.mark.unit
class TestGetExchangeDataFetcher:
    def test_returns_binance_fetcher(self):
        from data.data_fetcher import BinanceDataFetcher, get_data_fetcher

        fetcher = get_data_fetcher("binance")
        assert isinstance(fetcher, BinanceDataFetcher)

    def test_returns_okx_fetcher(self):
        from data.data_fetcher import OkxDataFetcher, get_data_fetcher

        fetcher = get_data_fetcher("okx")
        assert isinstance(fetcher, OkxDataFetcher)

    def test_raises_on_unsupported_exchange(self):
        from data.data_fetcher import get_data_fetcher

        with pytest.raises(ValueError, match="Unsupported exchange"):
            get_data_fetcher("kraken")

    def test_case_insensitive_exchange_name(self):
        from data.data_fetcher import BinanceDataFetcher, get_data_fetcher

        assert isinstance(get_data_fetcher("Binance"), BinanceDataFetcher)
        assert isinstance(get_data_fetcher("BINANCE"), BinanceDataFetcher)


@pytest.mark.unit
class TestOkxIntervalConversion:
    def test_convert_hour_intervals(self):
        from data.data_fetcher import OkxDataFetcher

        fetcher = OkxDataFetcher()
        assert fetcher._convert_interval("1h") == "1H"
        assert fetcher._convert_interval("2h") == "2H"
        assert fetcher._convert_interval("4h") == "4H"

    def test_convert_day_interval(self):
        from data.data_fetcher import OkxDataFetcher

        fetcher = OkxDataFetcher()
        assert fetcher._convert_interval("1d") == "1D"

    def test_convert_minute_intervals(self):
        from data.data_fetcher import OkxDataFetcher

        fetcher = OkxDataFetcher()
        assert fetcher._convert_interval("1m") == "1m"
        assert fetcher._convert_interval("5m") == "5m"
        assert fetcher._convert_interval("15m") == "15m"

    def test_unknown_interval_defaults_to_1D(self):
        from data.data_fetcher import OkxDataFetcher

        fetcher = OkxDataFetcher()
        assert fetcher._convert_interval("unknown") == "1D"


@pytest.mark.unit
class TestSymbolNotFoundError:
    def test_is_exception(self):
        from data.data_fetcher import SymbolNotFoundError

        with pytest.raises(SymbolNotFoundError):
            raise SymbolNotFoundError("test")

    def test_message_preserved(self):
        from data.data_fetcher import SymbolNotFoundError

        with pytest.raises(SymbolNotFoundError, match="BTC not found"):
            raise SymbolNotFoundError("BTC not found")
