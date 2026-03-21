"""
StrategyScanner 단위 테스트

DB 의존성을 모킹하여 필터 및 분석 로직을 검증합니다.
"""

import pytest

from app.services.strategy_scanner import StrategyScanner, ScanConfig


@pytest.fixture
def scanner():
    return StrategyScanner()


class TestLiquidityFilter:
    def test_filters_low_amount(self, scanner, sample_candles):
        """거래대금 미달 종목 제외"""
        tickers, filtered = scanner._apply_liquidity_filter(
            sample_candles, min_amount=5_000_000_000, min_price=1000
        )
        # 999999 (거래대금 50,000)는 제외
        assert "999999" not in tickers
        assert len(tickers) == 3

    def test_filters_low_price(self, scanner, sample_candles):
        """최소 가격 미달 종목 제외"""
        tickers, filtered = scanner._apply_liquidity_filter(
            sample_candles, min_amount=0, min_price=1000
        )
        # 999999 (종가 510)는 제외
        assert "999999" not in tickers

    def test_all_pass(self, scanner, sample_candles):
        """필터 조건을 0으로 설정하면 전부 통과"""
        tickers, filtered = scanner._apply_liquidity_filter(
            sample_candles, min_amount=0, min_price=0
        )
        assert len(tickers) == 4

    def test_no_duplicates(self, scanner):
        """동일 ticker가 중복되지 않아야 함"""
        candles = [
            {"ticker": "005930", "open": 70000, "close": 72000, "volume": 1000000, "amount": 70000000000},
            {"ticker": "005930", "open": 70000, "close": 72000, "volume": 1000000, "amount": 70000000000},
        ]
        tickers, _ = scanner._apply_liquidity_filter(candles, min_amount=0, min_price=0)
        assert len(tickers) == 1


class TestShouldExclude:
    def test_exclude_preferred(self, scanner):
        """우선주 제외"""
        assert scanner._should_exclude("005935", "삼성전자우", True, None) is True

    def test_exclude_warning(self, scanner):
        """시장경보 종목 제외"""
        assert scanner._should_exclude("111111", "테스트종목", False, "관리종목") is True

    def test_exclude_etf_keyword(self, scanner):
        """ETF 키워드 포함 종목 제외"""
        assert scanner._should_exclude("123456", "KODEX200ETF", False, None) is True

    def test_exclude_non_numeric_ticker(self, scanner):
        """6자리 숫자가 아닌 종목코드 제외"""
        assert scanner._should_exclude("KS11", "KOSPI지수", False, None) is True

    def test_normal_stock_passes(self, scanner):
        """일반 종목은 통과"""
        assert scanner._should_exclude("005930", "삼성전자", False, None) is False


class TestBuildIndicatorMap:
    def test_basic_mapping(self, scanner):
        """지표 맵 구성 검증"""
        indicators = [
            {"ticker": "005930", "indicator_type": "MA", "params": '{"period": 20}', "value": 70000},
            {"ticker": "005930", "indicator_type": "HIGH", "params": '{"period": 20}', "value": 72000},
            {"ticker": "005930", "indicator_type": "ATR", "params": '{"period": 20}', "value": 1500},
            {"ticker": "005930", "indicator_type": "EMA_STAGE", "params": '{"medium": 20, "short": 5, "long": 40}', "value": 1},
        ]
        result = scanner._build_indicator_map(indicators)
        assert result["005930"]["MA_20"] == 70000
        assert result["005930"]["HIGH_20"] == 72000
        assert result["005930"]["ATR_20"] == 1500
        assert result["005930"]["EMA_STAGE"] == 1

    def test_ignores_other_periods(self, scanner):
        """MA(20) 외 다른 기간은 무시"""
        indicators = [
            {"ticker": "005930", "indicator_type": "MA", "params": '{"period": 60}', "value": 65000},
        ]
        result = scanner._build_indicator_map(indicators)
        assert "MA_20" not in result.get("005930", {})


class TestAnalyzeSignals:
    def test_signal_detected(self, scanner):
        """조건 충족 시 신호 생성"""
        tickers = ["005930"]
        candle_map = {
            "005930": {"open": 70000, "close": 73000, "volume": 1000000, "amount": 73000000000}
        }
        ind_map = {
            "005930": {"MA_20": 71000, "HIGH_20": 72000, "ATR_20": 1500, "EMA_STAGE": 1}
        }
        name_map = {"005930": "삼성전자"}

        signals = scanner._analyze_signals(tickers, candle_map, ind_map, name_map)
        assert len(signals) == 1
        assert signals[0]["ticker"] == "005930"
        assert signals[0]["strength"] > 0

    def test_no_signal_below_ma(self, scanner):
        """MA(20) 아래이면 신호 없음"""
        tickers = ["005930"]
        candle_map = {
            "005930": {"open": 70000, "close": 69000, "volume": 1000000, "amount": 69000000000}
        }
        ind_map = {
            "005930": {"MA_20": 71000, "HIGH_20": 68000}
        }
        name_map = {"005930": "삼성전자"}

        signals = scanner._analyze_signals(tickers, candle_map, ind_map, name_map)
        assert len(signals) == 0

    def test_no_signal_negative_candle(self, scanner):
        """음봉이면 신호 없음"""
        tickers = ["005930"]
        candle_map = {
            "005930": {"open": 74000, "close": 73000, "volume": 1000000, "amount": 73000000000}
        }
        ind_map = {
            "005930": {"MA_20": 71000, "HIGH_20": 72000}
        }
        name_map = {"005930": "삼성전자"}

        signals = scanner._analyze_signals(tickers, candle_map, ind_map, name_map)
        assert len(signals) == 0

    def test_skip_missing_indicators(self, scanner):
        """지표 데이터 없으면 건너뜀"""
        tickers = ["005930"]
        candle_map = {
            "005930": {"open": 70000, "close": 73000, "volume": 1000000, "amount": 73000000000}
        }
        ind_map = {}  # 지표 없음
        name_map = {"005930": "삼성전자"}

        signals = scanner._analyze_signals(tickers, candle_map, ind_map, name_map)
        assert len(signals) == 0
