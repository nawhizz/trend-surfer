"""
시장 필터 확인 및 지표 저장 스크립트

KOSPI/KOSDAQ 지수의 60일 이동평균 기반 시장 필터 상태 확인

사용법:
    cd backend
    uv run ../scripts/check_market_filter.py --mode status --date 2026-01-16
    uv run ../scripts/check_market_filter.py --mode range --start 2026-01-01 --end 2026-01-16
    uv run ../scripts/check_market_filter.py --mode save --start 2025-01-01
"""

import argparse
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from app.services.market_filter import market_filter


def check_market_status(date: str):
    """단일 날짜 시장 상태 확인"""
    print("=" * 60)
    print(f"시장 상태 확인: {date}")
    print("=" * 60)

    status = market_filter.get_market_status(date)

    print(f"\n📊 KOSPI (KS11)")
    print(f"   종가: {status['kospi_close']}")
    print(f"   MA(60): {status['kospi_ma60']}")
    print(f"   MA 상회: {'✓' if status['kospi_above_ma'] else '✗'}")

    print(f"\n📊 KOSDAQ (KQ11)")
    print(f"   종가: {status['kosdaq_close']}")
    print(f"   MA(60): {status['kosdaq_ma60']}")
    print(f"   MA 상회: {'✓' if status['kosdaq_above_ma'] else '✗'}")

    print(f"\n🎯 시장 필터 결과")
    if status["is_bullish"] is True:
        print("   ✅ BULLISH - 신규 진입 허용")
    elif status["is_bullish"] is False:
        print("   ❌ BEARISH - 신규 진입 금지")
    else:
        print("   ⚠ 판단 불가 (데이터 부족)")


def check_market_range(start_date: str, end_date: str):
    """기간별 시장 상태 확인"""
    print("=" * 60)
    print(f"시장 상태 히스토리: {start_date} ~ {end_date}")
    print("=" * 60)

    from datetime import datetime, timedelta

    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        status = market_filter.get_market_status(date_str)

        if status["kospi_close"] is not None:  # 거래일만 출력
            bullish = "🟢" if status["is_bullish"] else "🔴"
            kospi = f"KOSPI: {status['kospi_close']:.2f} {'>' if status['kospi_above_ma'] else '<'} {status['kospi_ma60']:.2f}"
            kosdaq = f"KOSDAQ: {status['kosdaq_close']:.2f} {'>' if status['kosdaq_above_ma'] else '<'} {status['kosdaq_ma60']:.2f}"
            print(f"{date_str} {bullish} | {kospi} | {kosdaq}")

        current += timedelta(days=1)


def save_market_indicators(start_date: str, end_date: str = None):
    """지수 MA(60) 지표를 DB에 저장"""
    print("=" * 60)
    print(f"지수 MA(60) 지표 저장: {start_date} ~ {end_date or '오늘'}")
    print("=" * 60)

    saved = market_filter.save_market_indicators_to_db(start_date, end_date)
    print(f"\n총 {saved}개 지표 저장 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="시장 필터 확인")
    parser.add_argument(
        "--mode",
        choices=["status", "range", "save"],
        default="status",
        help="모드: status(단일날짜), range(기간), save(DB저장)",
    )
    parser.add_argument("--date", type=str, help="기준일 (YYYY-MM-DD)")
    parser.add_argument("--start", type=str, help="시작일 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="종료일 (YYYY-MM-DD)")

    args = parser.parse_args()

    if args.mode == "status":
        date = args.date or args.start
        if not date:
            print("--date 또는 --start 옵션이 필요합니다.")
            sys.exit(1)
        check_market_status(date)
    elif args.mode == "range":
        if not args.start or not args.end:
            print("--start와 --end 옵션이 필요합니다.")
            sys.exit(1)
        check_market_range(args.start, args.end)
    elif args.mode == "save":
        if not args.start:
            print("--start 옵션이 필요합니다.")
            sys.exit(1)
        save_market_indicators(args.start, args.end)
