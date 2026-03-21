"""
전략 신호 조회 API 엔드포인트
"""

from datetime import datetime
from fastapi import APIRouter, Query

from app.services.strategy_scanner import strategy_scanner, ScanConfig
from app.services.market_filter import market_filter

router = APIRouter()


@router.get("/scan")
def scan_signals(
    date: str = Query(default=None, description="기준 날짜 (YYYY-MM-DD, 기본: 오늘)"),
    min_amount: int = Query(default=5_000_000_000, description="최소 거래대금 (원)"),
    min_price: int = Query(default=1_000, description="최소 주가 (원)"),
):
    """
    전략 신호 스캔 실행

    추세추종 전략 조건(MA20 위 + 20일 신고가 돌파 + 양봉)을 만족하는 종목을 반환합니다.
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    config = ScanConfig(
        target_date=target_date,
        min_amount=min_amount,
        min_price=min_price,
    )
    signals = strategy_scanner.scan(config)

    return {
        "date": target_date,
        "count": len(signals),
        "signals": signals,
    }


@router.get("/market-status")
def get_market_status(
    date: str = Query(default=None, description="기준 날짜 (YYYY-MM-DD, 기본: 오늘)"),
):
    """
    시장 상태 조회 (KOSPI/KOSDAQ MA60 기준)
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    status = market_filter.get_full_market_status(target_date)
    return status
