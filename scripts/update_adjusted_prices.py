"""
수정주가 이벤트 감지 및 과거 데이터 백필

액면분할, 무상증자 등 수정주가 이벤트 발생 시:
1. KRX API 당일 시세와 DB 전일 종가를 비교하여 이벤트 감지
2. 대상 종목 목록을 테이블 형식으로 출력
3. hybrid_collector로 과거 데이터 백필 (FDR 수정주가 기반)
4. 지표 재계산
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.krx_collector import krx_collector
from app.services.hybrid_collector import hybrid_collector
from app.services.indicator_calculator import indicator_calculator
from app.db.client import supabase
from app.core.logger import get_logger

logger = get_logger("update_adjusted_prices")


def normalize_date(date_str: str) -> tuple[str, str]:
    """입력 날짜를 (YYYYMMDD, YYYY-MM-DD) 튜플로 변환"""
    clean = date_str.replace("-", "")
    dt = datetime.strptime(clean, "%Y%m%d")
    return dt.strftime("%Y%m%d"), dt.strftime("%Y-%m-%d")


def fetch_db_latest_closes(db_tickers: set, before_date: str) -> dict:
    """
    target_date 직전 거래일의 종가를 DB에서 조회.
    최대 7일 전까지 탐색하여 공휴일/연휴 대응.

    Returns: {ticker: {"close": float, "date": str}}
    """
    dt = datetime.strptime(before_date, "%Y-%m-%d")

    for days_back in range(1, 8):
        check_date = dt - timedelta(days=days_back)
        check_str = check_date.strftime("%Y-%m-%d")

        try:
            resp = supabase.table("daily_candles") \
                .select("ticker, close") \
                .eq("date", check_str) \
                .execute()
        except Exception as e:
            logger.error(f"DB 조회 오류 ({check_str}): {e}")
            continue

        if resp.data and len(resp.data) > 0:
            logger.info(f"DB 전일 종가 기준일: {check_str} ({len(resp.data)}건)")
            return {
                row['ticker']: {"close": row['close'], "date": check_str}
                for row in resp.data
                if row['ticker'] in db_tickers
            }

    logger.warning("최근 7일 내 DB 데이터 없음")
    return {}


def detect_adjustments(
    today_candles: list[dict],
    db_closes: dict,
    ticker_name_map: dict,
    threshold: float,
) -> list[dict]:
    """
    KRX 당일 시세와 DB 전일 종가를 비교하여 수정주가 이벤트 후보 감지.

    비교 방식: implied_prev = today_close / (1 + change_rate/100)
    DB 전일 종가와 implied_prev의 차이가 threshold 초과 시 후보로 판정.
    """
    candidates = []

    for item in today_candles:
        ticker = item['ticker']
        if ticker not in db_closes:
            continue

        today_close = item['close']
        rate = item['change_rate']

        # 등락률로 추정 전일 종가 계산
        if rate == 0:
            implied_prev = float(today_close)
        else:
            implied_prev = today_close / (1 + rate / 100.0)

        actual_prev = db_closes[ticker]['close']
        db_date = db_closes[ticker]['date']

        if actual_prev == 0:
            continue

        diff_ratio = abs(implied_prev - actual_prev) / actual_prev

        if diff_ratio > threshold:
            candidates.append({
                "ticker": ticker,
                "name": ticker_name_map.get(ticker, "?"),
                "db_close": actual_prev,
                "db_date": db_date,
                "implied_prev": implied_prev,
                "today_close": today_close,
                "change_rate": rate,
                "diff_ratio": diff_ratio,
            })

    # 차이율 내림차순 정렬
    candidates.sort(key=lambda x: x['diff_ratio'], reverse=True)
    return candidates


def print_detection_summary(candidates: list[dict]):
    """감지된 종목 정보를 테이블 형식으로 출력"""
    logger.info("=" * 70)
    logger.info(f"수정주가 이벤트 감지: {len(candidates)}건")
    logger.info("-" * 70)
    logger.info(f"{'종목코드':<8} {'종목명':<14} {'DB종가':>10} {'추정전일':>10} {'차이':>8}")
    logger.info("-" * 70)
    for c in candidates:
        logger.info(
            f"{c['ticker']:<8} {c['name']:<14} "
            f"{c['db_close']:>10,} {c['implied_prev']:>10,.0f} "
            f"{c['diff_ratio']*100:>7.1f}%"
        )
    logger.info("=" * 70)


def backfill_and_recalculate(candidates: list[dict], backfill_start: str, backfill_end: str):
    """hybrid_collector로 FDR 수정주가 기반 백필 후 지표 재계산"""
    ticker_list = [c['ticker'] for c in candidates]

    logger.info(f"백필 시작: {backfill_start} ~ {backfill_end} ({len(ticker_list)}종목)")
    hybrid_collector.backfill_hybrid(backfill_start, backfill_end, ticker_list)
    logger.info("백필 완료")

    logger.info(f"지표 재계산 시작: {len(ticker_list)}종목")
    indicator_calculator.calculate_and_save_for_all_tickers(
        start_date=backfill_start,
        end_date=backfill_end,
        ticker_list=ticker_list,
    )
    logger.info("지표 재계산 완료")

    # 결과 요약
    logger.info("=" * 70)
    logger.info("수정주가 업데이트 완료 요약")
    logger.info(f"  대상 종목: {len(ticker_list)}개")
    for c in candidates:
        logger.info(f"    - {c['ticker']} {c['name']}")
    logger.info(f"  백필 기간: {backfill_start} ~ {backfill_end}")
    logger.info("=" * 70)


def detect_and_update(target_date_str=None, threshold=0.20, backfill_start_date="2020-01-01"):
    """
    메인 실행 함수.
    1. KRX API로 당일 시세 조회
    2. DB 전일 종가와 비교하여 수정주가 이벤트 감지
    3. 감지 시 백필 + 지표 재계산
    """
    # 1. 날짜 정규화
    if not target_date_str:
        target_date_str = datetime.now().strftime("%Y-%m-%d")
    api_date, iso_date = normalize_date(target_date_str)

    # 2. KRX 공식 API로 당일 시세 조회
    # KRX API가 0건이면 당일 데이터 미공시(휴장일 또는 마감 후 미반영)로 판단하고 종료.
    # (FDR 폴백은 외부 GitHub 캐시 지연으로 불안정하고, 같은 날 데이터는 FDR에도 없어 무의미하므로 제거)
    logger.info(f"KRX 당일 시세 조회: {api_date}")
    today_candles = krx_collector.fetch_market_ohlcv_by_date(api_date)
    if not today_candles:
        logger.info("당일 시세 데이터 없음 (휴장일 또는 데이터 미공시). 종료.")
        return
    logger.info(f"KRX 시세 {len(today_candles)}건 조회 완료")

    # 3. DB 종목 마스터 조회 (ticker + name)
    try:
        resp = supabase.table("stocks").select("ticker, name").execute()
        db_tickers = {item['ticker'] for item in resp.data}
        ticker_name_map = {item['ticker']: item['name'] for item in resp.data}
    except Exception as e:
        logger.error(f"종목 마스터 조회 실패: {e}")
        return

    # API 결과를 DB 종목으로 필터링
    today_candles = [c for c in today_candles if c['ticker'] in db_tickers]
    logger.info(f"DB 등록 종목 기준 {len(today_candles)}건 대상")

    # 4. DB 전일 종가 조회 (최대 7일 전까지 탐색)
    db_closes = fetch_db_latest_closes(db_tickers, iso_date)
    if not db_closes:
        logger.warning("DB 전일 종가 없음. 수정주가 검증 불가.")
        return

    # 5. 수정주가 이벤트 감지
    candidates = detect_adjustments(today_candles, db_closes, ticker_name_map, threshold)

    # 6. 결과 출력
    if not candidates:
        logger.info("수정주가 이벤트 감지 없음")
        return

    print_detection_summary(candidates)

    # 7. 백필 + 지표 재계산
    backfill_end = db_closes[candidates[0]['ticker']]['date']
    backfill_and_recalculate(candidates, backfill_start_date, backfill_end)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="수정주가 이벤트 감지 및 백필")
    parser.add_argument("--date", help="대상일 (YYYYMMDD 또는 YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument("--threshold", type=float, default=0.20,
                        help="차이 임계값 (0.20 = 20%%, 기본: 0.20)")
    parser.add_argument("--start_date", default="2020-01-01",
                        help="백필 시작일 YYYY-MM-DD (기본: 2020-01-01)")
    args = parser.parse_args()

    detect_and_update(args.date, args.threshold, args.start_date)
