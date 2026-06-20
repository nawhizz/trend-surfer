"""
BacktestEngine 진입가 가드 단위 테스트

결손 캔들(open=0 등)로 entry_price<=0 포지션이 생성되어
이후 손익률 계산에서 ZeroDivisionError가 나는 기존 버그를 막는 가드를 검증한다.

DB 비의존: 엔진의 순수 헬퍼 _is_valid_entry_price만 테스트한다.
"""

import pytest

from app.backtest.engine import BacktestEngine
from app.backtest.strategies.trend_following import TrendFollowingStrategy


@pytest.fixture
def engine():
    # DB 저장 비활성화로 순수 객체 생성 (헬퍼만 테스트하므로 DB 접근 없음)
    return BacktestEngine(
        strategy=TrendFollowingStrategy(),
        initial_capital=100_000_000,
        save_to_db=False,
    )


def test_zero_entry_price_is_invalid(engine):
    """entry_price=0 (결손 캔들 open=0) → 진입 불가"""
    assert engine._is_valid_entry_price(0) is False


def test_negative_entry_price_is_invalid(engine):
    """entry_price<0 (비정상 데이터) → 진입 불가"""
    assert engine._is_valid_entry_price(-100) is False


def test_positive_entry_price_is_valid(engine):
    """정상 시가 → 진입 가능"""
    assert engine._is_valid_entry_price(57600) is True
