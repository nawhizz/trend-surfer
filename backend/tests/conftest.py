"""
테스트 공통 Fixtures

외부 의존성(Supabase, FDR 등)을 모킹하여
순수 단위 테스트를 실행할 수 있도록 합니다.
"""

import pytest
import numpy as np


@pytest.fixture
def sample_close_prices():
    """테스트용 종가 배열 (50일치)"""
    np.random.seed(42)
    # 기준가 10,000에서 시작하여 약간의 변동
    base = 10000
    changes = np.random.normal(0, 100, 50)
    prices = np.cumsum(changes) + base
    return prices.astype(np.float64)


@pytest.fixture
def sample_ohlc_prices(sample_close_prices):
    """테스트용 OHLC 배열"""
    close = sample_close_prices
    high = close + np.abs(np.random.normal(0, 50, len(close)))
    low = close - np.abs(np.random.normal(0, 50, len(close)))
    open_p = close + np.random.normal(0, 30, len(close))
    return {
        "open": open_p.astype(np.float64),
        "high": high.astype(np.float64),
        "low": low.astype(np.float64),
        "close": close,
    }


@pytest.fixture
def sample_candles():
    """테스트용 일봉 데이터 리스트"""
    return [
        {"ticker": "005930", "open": 70000, "close": 72000, "volume": 1000000, "amount": 70000000000},
        {"ticker": "000660", "open": 150000, "close": 148000, "volume": 500000, "amount": 74000000000},
        {"ticker": "035420", "open": 300000, "close": 310000, "volume": 200000, "amount": 62000000000},
        {"ticker": "999999", "open": 500, "close": 510, "volume": 100, "amount": 50000},  # 저유동성
    ]


@pytest.fixture
def sample_stock_info():
    """테스트용 종목 정보"""
    return [
        {"ticker": "005930", "name": "삼성전자", "is_preferred": False, "warning_type": None},
        {"ticker": "005935", "name": "삼성전자우", "is_preferred": True, "warning_type": None},
        {"ticker": "000660", "name": "SK하이닉스", "is_preferred": False, "warning_type": None},
        {"ticker": "035420", "name": "NAVER", "is_preferred": False, "warning_type": None},
        {"ticker": "900090", "name": "테스트ETF", "is_preferred": False, "warning_type": None},
        {"ticker": "111111", "name": "관리종목테스트", "is_preferred": False, "warning_type": "관리종목"},
    ]
