"""
IndicatorCalculator 단위 테스트

외부 의존성 없이 지표 계산 로직만 검증합니다.
"""

import numpy as np
import pytest

from app.services.indicator_calculator import IndicatorCalculator


@pytest.fixture
def calc():
    return IndicatorCalculator()


class TestSMA:
    def test_sma_basic(self, calc):
        """SMA(5) 기본 계산 검증"""
        prices = np.array([10, 20, 30, 40, 50], dtype=np.float64)
        result = calc.calculate_sma(prices, 5)
        assert result[-1] == pytest.approx(30.0)

    def test_sma_nan_prefix(self, calc):
        """SMA 앞부분은 NaN이어야 함"""
        prices = np.arange(1, 11, dtype=np.float64)
        result = calc.calculate_sma(prices, 5)
        assert np.isnan(result[0])
        assert np.isnan(result[3])
        assert not np.isnan(result[4])

    def test_sma_with_sample_data(self, calc, sample_close_prices):
        """샘플 데이터로 SMA(20) 계산"""
        result = calc.calculate_sma(sample_close_prices, 20)
        # 20일차부터 유효한 값
        assert np.isnan(result[18])
        assert not np.isnan(result[19])


class TestEMA:
    def test_ema_basic(self, calc):
        """EMA(3) 기본 계산 - 상승 추세에서 EMA >= SMA"""
        prices = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=np.float64)
        result = calc.calculate_ema(prices, 3)
        sma_result = calc.calculate_sma(prices, 3)
        # 충분한 데이터에서 상승 추세 시 EMA >= SMA
        assert result[-1] >= sma_result[-1]

    def test_ema_length(self, calc, sample_close_prices):
        """EMA 결과 길이가 입력과 동일"""
        result = calc.calculate_ema(sample_close_prices, 20)
        assert len(result) == len(sample_close_prices)


class TestATR:
    def test_atr_positive(self, calc, sample_ohlc_prices):
        """ATR은 항상 양수"""
        result = calc.calculate_atr(
            sample_ohlc_prices["high"],
            sample_ohlc_prices["low"],
            sample_ohlc_prices["close"],
            period=20,
        )
        valid = result[~np.isnan(result)]
        assert all(v > 0 for v in valid)

    def test_atr_nan_prefix(self, calc, sample_ohlc_prices):
        """ATR 앞부분은 NaN"""
        result = calc.calculate_atr(
            sample_ohlc_prices["high"],
            sample_ohlc_prices["low"],
            sample_ohlc_prices["close"],
            period=20,
        )
        assert np.isnan(result[0])


class TestPeriodHigh:
    def test_period_high_excludes_today(self, calc):
        """당일 제외 최고가 검증"""
        # 인덱스: 0  1  2  3  4
        prices = np.array([100, 200, 150, 180, 300], dtype=np.float64)
        result = calc.calculate_period_high(prices, 3)
        # i=3: max(prices[0:3]) = max(100, 200, 150) = 200
        assert result[3] == 200.0
        # i=4: max(prices[1:4]) = max(200, 150, 180) = 200
        assert result[4] == 200.0

    def test_period_high_nan_for_insufficient_data(self, calc):
        """데이터 부족 시 NaN"""
        prices = np.array([100, 200, 150], dtype=np.float64)
        result = calc.calculate_period_high(prices, 5)
        assert all(np.isnan(result))


class TestRSI:
    def test_rsi_range(self, calc, sample_close_prices):
        """RSI는 0~100 범위"""
        result = calc.calculate_rsi(sample_close_prices, 14)
        valid = result[~np.isnan(result)]
        assert all(0 <= v <= 100 for v in valid)


class TestEMAStage:
    def test_stage_1_uptrend(self, calc):
        """스테이지 1 (안정 상승기): 단기 > 중기 > 장기"""
        # 강한 상승 추세 데이터 생성
        prices = np.arange(1, 101, dtype=np.float64) * 100
        result = calc.calculate_ema_stage(prices)
        # 충분한 데이터 이후에는 스테이지 1이어야 함
        assert result[-1] == 1.0

    def test_stage_4_downtrend(self, calc):
        """스테이지 4 (안정 하락기): 장기 > 중기 > 단기"""
        # 강한 하락 추세 데이터
        prices = np.arange(100, 0, -1, dtype=np.float64) * 100
        result = calc.calculate_ema_stage(prices)
        assert result[-1] == 4.0


class TestBuildIndicatorRecords:
    def test_filters_nan(self, calc):
        """NaN 값은 레코드에 포함되지 않아야 함"""
        dates = np.array(["2025-01-01", "2025-01-02", "2025-01-03"])
        values = np.array([np.nan, 100.0, np.nan])
        records = calc._build_indicator_records(
            ticker="005930", dates=dates, values=values,
            indicator_type="MA", params={"period": 20},
        )
        assert len(records) == 1
        assert records[0]["value"] == 100.0

    def test_respects_start_date(self, calc):
        """start_date 이전 데이터는 제외"""
        dates = np.array(["2025-01-01", "2025-01-02", "2025-01-03"])
        values = np.array([100.0, 200.0, 300.0])
        records = calc._build_indicator_records(
            ticker="005930", dates=dates, values=values,
            indicator_type="MA", params={"period": 20},
            start_date="2025-01-02",
        )
        assert len(records) == 2
        assert records[0]["date"] == "2025-01-02"
