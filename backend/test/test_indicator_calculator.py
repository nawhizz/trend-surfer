"""
이동평균 계산기 테스트 스크립트

ta-lib으로 SMA/EMA 계산 후 DB 저장 테스트
"""

import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.services.indicator_calculator import indicator_calculator


def test_single_ticker():
    """단일 종목 테스트 (삼성전자)"""
    print("=" * 50)
    print("단일 종목 테스트: 005930 (삼성전자)")
    print("=" * 50)

    # 1. 이동평균 계산
    indicators = indicator_calculator.calculate_all_ma_for_ticker(
        ticker="005930",
        start_date="2025-01-01",  # 최근 1년만 저장
        end_date=None,
    )

    print(f"\n계산된 지표 수: {len(indicators)}")

    # 샘플 출력
    if indicators:
        print("\n--- 샘플 데이터 (처음 5개) ---")
        for ind in indicators[:5]:
            print(
                f"  {ind['date']} | {ind['indicator_type']} | {ind['params']} | {ind['value']}"
            )

        print("\n--- 샘플 데이터 (마지막 5개) ---")
        for ind in indicators[-5:]:
            print(
                f"  {ind['date']} | {ind['indicator_type']} | {ind['params']} | {ind['value']}"
            )

    # 2. DB 저장
    print("\n--- DB 저장 ---")
    saved = indicator_calculator.save_indicators_to_db(indicators)
    print(f"저장 완료: {saved} records")


def test_calculation_only():
    """DB 저장 없이 계산만 테스트"""
    print("=" * 50)
    print("계산 전용 테스트 (DB 저장 안함)")
    print("=" * 50)

    import numpy as np

    # 샘플 데이터
    close_prices = np.array(
        [100, 102, 101, 103, 105, 104, 106, 108, 107, 110], dtype=np.float64
    )

    # SMA 5일 테스트
    sma_5 = indicator_calculator.calculate_sma(close_prices, 5)
    print(f"\n종가: {close_prices}")
    print(f"SMA(5): {sma_5}")

    # EMA 5일 테스트
    ema_5 = indicator_calculator.calculate_ema(close_prices, 5)
    print(f"EMA(5): {ema_5}")


def test_multiple_tickers():
    """여러 종목 테스트"""
    print("=" * 50)
    print("여러 종목 테스트")
    print("=" * 50)

    # 테스트할 종목 리스트
    test_tickers = ["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, NAVER

    indicator_calculator.calculate_and_save_for_all_tickers(
        start_date="2025-01-01",
        end_date=None,
        ticker_list=test_tickers,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="이동평균 계산기 테스트")
    parser.add_argument(
        "--mode",
        choices=["calc", "single", "multi"],
        default="calc",
        help="테스트 모드: calc(계산만), single(단일종목), multi(여러종목)",
    )

    args = parser.parse_args()

    if args.mode == "calc":
        test_calculation_only()
    elif args.mode == "single":
        test_single_ticker()
    elif args.mode == "multi":
        test_multiple_tickers()
