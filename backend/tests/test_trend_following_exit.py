"""
TrendFollowingStrategy.check_exit_signal 보조 청산(EMA 구조) 단위 테스트

DB 비의존 순수 함수. 손절/트레일링이 발동하지 않는 값으로 고정하여
EMA 보조 청산(기울기 급락 / 2일 연속 이탈)만 검증한다.
"""

import pytest

from app.backtest.strategies.trend_following import TrendFollowingStrategy
from app.backtest.strategies.base import SignalData


@pytest.fixture
def strategy():
    return TrendFollowingStrategy()


def make_data(close, ema50, ema50_slope, atr20=5.0):
    """손절/트레일링 미발동 조건의 SignalData 생성 헬퍼"""
    return SignalData(
        date="2025-01-10",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        ema50=ema50,
        ema50_slope=ema50_slope,
        atr20=atr20,
    )


# 공통 진입 컨텍스트: 손절/트레일링이 절대 발동하지 않도록 넉넉히 설정
ENTRY_PRICE = 100.0
INITIAL_STOP = 1.0       # 종가가 이보다 훨씬 위라 STOP_LOSS 미발동
HIGHEST_CLOSE = 100.0    # 트레일링: highest - 2.5*atr = 100 - 12.5 = 87.5 미만일 때만 발동


def test_no_exit_when_above_ema(strategy):
    """종가 > 50EMA 이고 다른 청산 조건 없으면 None"""
    data = make_data(close=99.0, ema50=95.0, ema50_slope=0.1)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=0,
    )
    assert result is None


def test_immediate_exit_on_steep_slope(strategy):
    """종가<50EMA AND 기울기<-0.3 → 즉시 EMA_STRUCTURE_EXIT (ema_below_days 무관)"""
    data = make_data(close=94.0, ema50=95.0, ema50_slope=-0.5)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=1,
    )
    assert result == "EMA_STRUCTURE_EXIT"


def test_no_exit_below_ema_first_day(strategy):
    """종가<50EMA 이지만 기울기 완만(-0.1)하고 1일째 이탈이면 청산 안 함"""
    data = make_data(close=94.0, ema50=95.0, ema50_slope=-0.1)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=1,
    )
    assert result is None


def test_exit_on_two_day_below_ema(strategy):
    """종가<50EMA 이고 기울기 완만(-0.1)해도 2일 연속 이탈이면 EMA_STRUCTURE_EXIT"""
    data = make_data(close=94.0, ema50=95.0, ema50_slope=-0.1)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=2,
    )
    assert result == "EMA_STRUCTURE_EXIT"
