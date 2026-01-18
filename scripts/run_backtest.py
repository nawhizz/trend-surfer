"""
백테스트 실행 스크립트

사용법:
    cd backend
    uv run ../scripts/run_backtest.py --start 2024-01-01 --end 2025-12-31
    uv run ../scripts/run_backtest.py --start 2024-01-01 --ticker 005930
    uv run ../scripts/run_backtest.py --start 2024-01-01 --output ./results  # CSV 출력
"""

import argparse
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from app.backtest.engine import BacktestEngine
from app.backtest.strategies.sma_breakout import SmaBreakoutStrategy
from app.backtest.result import BacktestResult


def get_active_tickers() -> list[str]:
    """
    활성 종목 목록 조회 (보통주만)
    
    Supabase 기본 limit(1000) 제한을 우회하기 위해(!!!)
    페이지네이션으로 전체 종목을 조회합니다.
    """
    from app.db.client import supabase

    all_tickers = []
    page_size = 1000
    offset = 0

    while True:
        response = (
            supabase.table("stocks")
            .select("ticker")
            .eq("is_active", True)
            .eq("is_preferred", False)
            .neq("market", "INDEX")
            .range(offset, offset + page_size - 1)
            .execute()
        )

        if not response.data:
            break

        all_tickers.extend([row["ticker"] for row in response.data])

        # 다음 페이지가 없으면 종료
        if len(response.data) < page_size:
            break

        offset += page_size

    return all_tickers


def main():
    parser = argparse.ArgumentParser(description="백테스트 실행")
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="시작일 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="종료일 (YYYY-MM-DD), 기본값: 오늘",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="특정 종목만 테스트 (쉼표로 구분)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100_000_000,
        help="초기 자본금 (기본값: 1억원)",
    )
    parser.add_argument(
        "--risk",
        type=float,
        default=0.01,
        help="거래당 리스크 비율 (기본값: 0.01 = 1%%)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="결과 CSV 출력 경로 (예: ./results)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="sma",
        choices=["sma", "ema", "rsi", "trend"],
        help="전략 선택: sma (SMA 정배열), ema (EMA 정배열), rsi (RSI 스윙), trend (추세추종)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="상세 로그 숨기기",
    )

    args = parser.parse_args()

    # 종목 리스트 결정
    if args.ticker:
        tickers = [t.strip() for t in args.ticker.split(",")]
    else:
        print("활성 종목 목록 조회 중...")
        tickers = get_active_tickers()
        print(f"총 {len(tickers)}개 종목")

    # 종료일 처리
    end_date = args.end
    if not end_date:
        from datetime import datetime
        end_date = datetime.now().strftime("%Y-%m-%d")

    # 전략 생성
    if args.strategy == "ema":
        from app.backtest.strategies.ema_breakout import EmaBreakoutStrategy
        strategy = EmaBreakoutStrategy()
    elif args.strategy == "rsi":
        from app.backtest.strategies.rsi_swing import RsiSwingStrategy
        strategy = RsiSwingStrategy()
    elif args.strategy == "trend":
        from app.backtest.strategies.trend_following import TrendFollowingStrategy
        strategy = TrendFollowingStrategy()
    else:
        strategy = SmaBreakoutStrategy()

    # 엔진 생성 및 실행
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=args.capital,
        risk_per_trade=args.risk,
    )

    result = engine.run(
        start_date=args.start,
        end_date=end_date,
        tickers=tickers,
        verbose=not args.quiet,
    )

    # 상세 분석
    analyzer = BacktestResult(
        start_date=args.start,
        end_date=end_date,
        initial_capital=args.capital,
        final_equity=result["final_equity"],
        trades=result["trades"],
        daily_records=result["daily_records"],
    )

    # 상세 통계 출력
    analyzer.print_summary()

    # CSV 출력 (옵션)
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        trades_csv = os.path.join(args.output, "trades.csv")
        equity_csv = os.path.join(args.output, "equity.csv")
        analyzer.export_trades_csv(trades_csv)
        analyzer.export_equity_csv(equity_csv)


if __name__ == "__main__":
    main()
