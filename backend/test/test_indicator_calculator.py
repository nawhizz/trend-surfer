"""
기술적 지표 계산기 테스트 스크립트

ta-lib으로 SMA/EMA/ATR 계산 및 HIGH(기간 최고가) 계산 후 DB 저장 테스트

지원 지표:
- SMA (단순이동평균): 5, 10, 20, 60, 120, 240일
- EMA (지수이동평균): 5, 10, 20, 40, 50, 120, 200, 240일
- ATR (평균 변동성): 20일 - 추세추종 전략 손절가/포지션 사이징용
- HIGH (기간 최고 종가): 20일 - 추세추종 전략 돌파 신호용
"""

import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.services.indicator_calculator import indicator_calculator


def test_single_ticker():
    """단일 종목 테스트 (삼성전자) - 모든 지표 계산"""
    print("=" * 50)
    print("단일 종목 테스트: 005930 (삼성전자)")
    print("=" * 50)

    # 1. 모든 기술적 지표 계산 (MA + EMA + ATR + HIGH)
    indicators = indicator_calculator.calculate_all_indicators_for_ticker(
        ticker="005930",
        start_date="2025-01-01",  # 최근 1년만 저장
        end_date=None,
    )

    print(f"\n계산된 지표 수: {len(indicators)}")

    # 지표 유형별 개수 출력
    indicator_types = {}
    for ind in indicators:
        ind_type = ind['indicator_type']
        indicator_types[ind_type] = indicator_types.get(ind_type, 0) + 1
    
    print("\n--- 지표 유형별 개수 ---")
    for ind_type, count in sorted(indicator_types.items()):
        print(f"  {ind_type}: {count}개")

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
    """DB 저장 없이 계산만 테스트 (SMA, EMA, ATR, HIGH)"""
    print("=" * 50)
    print("계산 전용 테스트 (DB 저장 안함)")
    print("=" * 50)

    import numpy as np

    # 샘플 데이터 (10일치)
    close_prices = np.array(
        [100, 102, 101, 103, 105, 104, 106, 108, 107, 110], dtype=np.float64
    )
    high_prices = np.array(
        [101, 103, 102, 104, 106, 105, 107, 109, 108, 111], dtype=np.float64
    )
    low_prices = np.array(
        [99, 101, 100, 102, 104, 103, 105, 107, 106, 109], dtype=np.float64
    )

    # SMA 5일 테스트
    sma_5 = indicator_calculator.calculate_sma(close_prices, 5)
    print(f"\n종가: {close_prices}")
    print(f"SMA(5): {sma_5}")

    # EMA 5일 테스트
    ema_5 = indicator_calculator.calculate_ema(close_prices, 5)
    print(f"EMA(5): {ema_5}")

    # ATR 5일 테스트
    atr_5 = indicator_calculator.calculate_atr(high_prices, low_prices, close_prices, 5)
    print(f"\n고가: {high_prices}")
    print(f"저가: {low_prices}")
    print(f"ATR(5): {atr_5}")

    # HIGH 5일 테스트 (과거 5일 최고 종가, 당일 제외)
    high_5 = indicator_calculator.calculate_period_high(close_prices, 5)
    print(f"\nHIGH(5): {high_5}")
    print("설명: HIGH(5)[5] = max(close[0:5]) = max([100,102,101,103,105]) = 105")
    print(f"검증: HIGH(5)[5] = {high_5[5]} (예상: 105.0)")


def test_multiple_tickers():
    """여러 종목 테스트 - 모든 지표 계산"""
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


def test_strategy_indicators():
    """추세추종 전략용 지표만 테스트 (ATR, HIGH 중심)"""
    print("=" * 50)
    print("추세추종 전략용 지표 테스트: 005930 (삼성전자)")
    print("=" * 50)

    # 모든 지표 계산
    indicators = indicator_calculator.calculate_all_indicators_for_ticker(
        ticker="005930",
        start_date="2025-01-01",
        end_date=None,
    )

    # ATR과 HIGH 지표만 필터링해서 출력
    atr_indicators = [i for i in indicators if i['indicator_type'] == 'ATR']
    high_indicators = [i for i in indicators if i['indicator_type'] == 'HIGH']

    print(f"\n--- ATR(20) 지표 ---")
    print(f"총 {len(atr_indicators)}개")
    if atr_indicators:
        print("마지막 5일:")
        for ind in atr_indicators[-5:]:
            print(f"  {ind['date']} | ATR(20) = {ind['value']}")

    print(f"\n--- HIGH(20) 지표 ---")
    print(f"총 {len(high_indicators)}개")
    if high_indicators:
        print("마지막 5일:")
        for ind in high_indicators[-5:]:
            print(f"  {ind['date']} | 20일 최고 종가 = {ind['value']}")

    # DB 저장 여부 확인
    user_input = input("\nDB에 저장하시겠습니까? (y/n): ")
    if user_input.lower() == 'y':
        saved = indicator_calculator.save_indicators_to_db(indicators)
        print(f"저장 완료: {saved} records")
    else:
        print("저장 취소됨")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="기술적 지표 계산기 테스트")
    parser.add_argument(
        "--mode",
        choices=["calc", "single", "multi", "strategy"],
        default="calc",
        help="테스트 모드: calc(계산만), single(단일종목), multi(여러종목), strategy(전략용 지표)",
    )

    args = parser.parse_args()

    if args.mode == "calc":
        test_calculation_only()
    elif args.mode == "single":
        test_single_ticker()
    elif args.mode == "multi":
        test_multiple_tickers()
    elif args.mode == "strategy":
        test_strategy_indicators()
