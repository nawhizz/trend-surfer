"""
지수 데이터 백필 스크립트

KOSPI(KS11)와 KOSDAQ(KQ11) 지수의 과거 데이터를 수집합니다.
시장 필터(Market Regime Filter) 기능에 사용됩니다.

사용법:
    cd backend
    uv run ../scripts/backfill_index.py --start 2024-01-01 --end 2026-01-17
"""

import argparse
import os
import sys
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from app.services.index_collector import index_collector


def main():
    parser = argparse.ArgumentParser(description="지수 데이터 백필")
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
        choices=["KS11", "KQ11"],
        help="특정 지수만 수집 (KS11=KOSPI, KQ11=KOSDAQ)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(f"지수 데이터 백필 시작")
    print(f"  기간: {args.start} ~ {args.end or '오늘'}")
    print(f"  대상: {args.ticker or '전체 (KS11, KQ11)'}")
    print("=" * 60)

    index_collector.fetch_index_candles(
        start_date=args.start,
        end_date=args.end,
        ticker=args.ticker,
    )

    print("=" * 60)
    print("백필 완료!")


if __name__ == "__main__":
    main()
