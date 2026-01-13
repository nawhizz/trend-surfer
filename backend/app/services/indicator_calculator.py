"""
기술적 지표 계산 서비스

ta-lib 패키지를 사용하여 다양한 기술적 지표를 계산하고 DB에 저장합니다.
현재 지원 지표:
- SMA (단순이동평균): 5, 10, 20, 60, 120, 240일
- EMA (지수이동평균): 5, 10, 20, 40, 50, 120, 200, 240일
"""

import json
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import talib

from app.db.client import supabase


class IndicatorCalculator:
    """기술적 지표 계산 및 DB 저장을 담당하는 클래스"""

    # 계산할 이동평균 기간 설정
    SMA_PERIODS = [5, 10, 20, 60, 120, 240]
    EMA_PERIODS = [5, 10, 20, 40, 50, 120, 200, 240]

    def __init__(self):
        pass

    # ========================================
    # 이동평균 계산 함수
    # ========================================

    def calculate_sma(self, close_prices: np.ndarray, period: int) -> np.ndarray:
        """
        단순이동평균(SMA) 계산

        Args:
            close_prices: 종가 배열 (오래된 날짜 → 최신 날짜 순서)
            period: 이동평균 기간

        Returns:
            SMA 값 배열 (앞부분은 NaN)
        """
        return talib.SMA(close_prices, timeperiod=period)

    def calculate_ema(self, close_prices: np.ndarray, period: int) -> np.ndarray:
        """
        지수이동평균(EMA) 계산

        Args:
            close_prices: 종가 배열 (오래된 날짜 → 최신 날짜 순서)
            period: 이동평균 기간

        Returns:
            EMA 값 배열 (앞부분은 NaN)
        """
        return talib.EMA(close_prices, timeperiod=period)

    # ========================================
    # 데이터 조회 함수
    # ========================================

    def fetch_candles(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        특정 종목의 일봉 데이터 조회

        Args:
            ticker: 종목 코드
            start_date: 시작일 (YYYY-MM-DD), None이면 전체
            end_date: 종료일 (YYYY-MM-DD), None이면 전체

        Returns:
            일봉 DataFrame (date, close 컬럼 포함)
        """
        query = (
            supabase.table("daily_candles")
            .select("date, close")
            .eq("ticker", ticker)
            .order("date", desc=False)  # 오래된 날짜부터 정렬 (ta-lib 입력 순서)
        )

        if start_date:
            query = query.gte("date", start_date)
        if end_date:
            query = query.lte("date", end_date)

        # Supabase 기본 row limit이 있으므로 페이징 처리
        all_data = []
        offset = 0
        limit = 1000

        while True:
            response = query.range(offset, offset + limit - 1).execute()
            rows = response.data

            if not rows:
                break

            all_data.extend(rows)
            offset += limit

            if len(rows) < limit:
                break

        df = pd.DataFrame(all_data)

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df["close"] = pd.to_numeric(df["close"], errors="coerce")

        return df

    # ========================================
    # 지표 계산 및 저장
    # ========================================

    def calculate_all_ma_for_ticker(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """
        특정 종목의 모든 이동평균 계산

        Args:
            ticker: 종목 코드
            start_date: 계산 시작일 (YYYY-MM-DD)
            end_date: 계산 종료일 (YYYY-MM-DD)

        Returns:
            계산된 지표 딕셔너리 리스트
        """
        print(f"[{datetime.now()}] Calculating MA for {ticker}...")

        # 1. 일봉 데이터 조회 (이동평균 계산을 위해 충분한 과거 데이터 필요)
        # 가장 긴 이동평균 기간(240일)을 고려하여 여유있게 조회
        df = self.fetch_candles(ticker, start_date=None, end_date=end_date)

        if df.empty:
            print(f"No candle data found for {ticker}")
            return []

        if len(df) < max(self.SMA_PERIODS + self.EMA_PERIODS):
            print(
                f"Insufficient data for {ticker}: {len(df)} rows (need at least {max(self.SMA_PERIODS + self.EMA_PERIODS)})"
            )
            # 데이터가 부족해도 계산 가능한 범위에서는 진행

        # 2. numpy 배열로 변환
        dates = df["date"].values
        close_prices = df["close"].values.astype(np.float64)

        # 3. 모든 SMA/EMA 계산
        indicators = []

        # SMA 계산
        for period in self.SMA_PERIODS:
            sma_values = self.calculate_sma(close_prices, period)
            indicators.extend(
                self._build_indicator_records(
                    ticker=ticker,
                    dates=dates,
                    values=sma_values,
                    indicator_type="MA",
                    params={"period": period},
                    start_date=start_date,
                )
            )

        # EMA 계산
        for period in self.EMA_PERIODS:
            ema_values = self.calculate_ema(close_prices, period)
            indicators.extend(
                self._build_indicator_records(
                    ticker=ticker,
                    dates=dates,
                    values=ema_values,
                    indicator_type="EMA",
                    params={"period": period},
                    start_date=start_date,
                )
            )

        print(f"Calculated {len(indicators)} indicator records for {ticker}")
        return indicators

    def _build_indicator_records(
        self,
        ticker: str,
        dates: np.ndarray,
        values: np.ndarray,
        indicator_type: str,
        params: dict,
        start_date: Optional[str] = None,
    ) -> list[dict]:
        """
        계산된 값을 DB 저장 형식의 레코드로 변환

        Args:
            ticker: 종목 코드
            dates: 날짜 배열
            values: 계산된 지표 값 배열
            indicator_type: 지표 유형 ('MA', 'EMA' 등)
            params: 파라미터 딕셔너리 ({"period": 5} 등)
            start_date: 저장 시작일 (이 날짜 이후만 저장)

        Returns:
            DB 저장용 레코드 리스트
        """
        records = []

        # params를 정렬된 JSON 문자열로 변환 (일관성 유지)
        params_json = json.dumps(params, sort_keys=True)

        for i, (date_val, value) in enumerate(zip(dates, values)):
            # NaN 값은 저장하지 않음 (이동평균 초기 구간)
            if np.isnan(value):
                continue

            # start_date 필터링
            date_str = str(date_val)
            if start_date and date_str < start_date:
                continue

            record = {
                "ticker": ticker,
                "date": date_str,
                "indicator_type": indicator_type,
                "params": params_json,
                "value": round(float(value), 2),  # 소수점 2자리까지
                "values": None,  # 단일 값 지표이므로 None
            }
            records.append(record)

        return records

    def save_indicators_to_db(self, indicators: list[dict]) -> int:
        """
        계산된 지표를 DB에 저장 (upsert)

        Args:
            indicators: 지표 레코드 리스트

        Returns:
            저장된 레코드 수
        """
        if not indicators:
            return 0

        chunk_size = 500  # Supabase 배치 크기

        total_saved = 0

        for i in range(0, len(indicators), chunk_size):
            chunk = indicators[i : i + chunk_size]

            try:
                # PK: (ticker, date, indicator_type, params)
                supabase.table("daily_technical_indicators").upsert(
                    chunk, on_conflict="ticker, date, indicator_type, params"
                ).execute()
                total_saved += len(chunk)
                print(f"Saved indicators {i} ~ {i + len(chunk)} / {len(indicators)}")

            except Exception as e:
                print(f"Error saving indicators: {e}")

        return total_saved

    # ========================================
    # 전체 종목 처리
    # ========================================

    def calculate_and_save_for_all_tickers(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ticker_list: Optional[list[str]] = None,
    ):
        """
        전체 또는 특정 종목들의 이동평균을 계산하고 DB에 저장

        Args:
            start_date: 계산 시작일 (YYYY-MM-DD)
            end_date: 계산 종료일 (YYYY-MM-DD)
            ticker_list: 처리할 종목 리스트 (None이면 모든 활성 종목)
        """
        # 1. 대상 종목 목록 조회
        if ticker_list:
            tickers = ticker_list
        else:
            try:
                # Supabase 기본 row limit(1000건) 대응을 위한 페이징 처리
                all_tickers = []
                offset = 0
                limit = 1000

                while True:
                    response = (
                        supabase.table("stocks")
                        .select("ticker")
                        .eq("is_active", True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )

                    if not response.data:
                        break

                    all_tickers.extend([row["ticker"] for row in response.data])
                    offset += limit

                    if len(response.data) < limit:
                        break

                tickers = all_tickers
                print(f"Loaded {len(tickers)} active tickers from DB.")

            except Exception as e:
                print(f"Error fetching ticker list: {e}")
                return


        print(f"Processing {len(tickers)} tickers...")

        # 2. 종목별 처리
        for idx, ticker in enumerate(tickers):
            try:
                # 이동평균 계산
                indicators = self.calculate_all_ma_for_ticker(
                    ticker, start_date, end_date
                )

                # DB 저장
                if indicators:
                    saved = self.save_indicators_to_db(indicators)
                    print(f"[{idx + 1}/{len(tickers)}] {ticker}: saved {saved} records")
                else:
                    print(f"[{idx + 1}/{len(tickers)}] {ticker}: no indicators to save")

            except Exception as e:
                print(f"[{idx + 1}/{len(tickers)}] Error processing {ticker}: {e}")


# 싱글톤 인스턴스
indicator_calculator = IndicatorCalculator()
