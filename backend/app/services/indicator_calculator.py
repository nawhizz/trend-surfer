"""
기술적 지표 계산 서비스

ta-lib 패키지를 사용하여 다양한 기술적 지표를 계산하고 DB에 저장합니다.
현재 지원 지표:
- SMA (단순이동평균): 5, 10, 20, 60, 120, 240일
- EMA (지수이동평균): 5, 10, 20, 40, 50, 120, 200, 240일
- EMA_SLOPE (EMA 기울기): 50일 (ATR 정규화)
- ATR (평균 변동성): 20일
- HIGH (기간 최고 종가): 10, 20일 (당일 제외, 과거 N일 기준)
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
    
    # 추세추종 전략용 지표 기간 설정
    ATR_PERIODS = [20]        # 손절가, 포지션 사이징, 트레일링 스탑용
    HIGH_PERIODS = [10, 20]   # 10일(불타기), 20일(신고가 돌파) 신호용
    RSI_PERIODS = [14]        # 역추세 스윙 전략용
    EMA_SLOPE_PERIODS = [50]  # EMA 기울기 계산용 (구조 필터)
    
    # 이동평균 스테이지 분석용 (고정)
    EMA_STAGE_PARAMS = {"short": 5, "medium": 20, "long": 40}

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
    # ATR (Average True Range) 계산
    # ========================================

    def calculate_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int,
    ) -> np.ndarray:
        """
        ATR (Average True Range) 계산
        
        True Range는 다음 세 값 중 최댓값:
        - |고가 - 저가|
        - |고가 - 전일 종가|
        - |저가 - 전일 종가|
        
        ATR = True Range의 N일 이동평균

        Args:
            high: 고가 배열 (오래된 날짜 → 최신 날짜 순서)
            low: 저가 배열
            close: 종가 배열
            period: ATR 기간

        Returns:
            ATR 값 배열 (앞부분은 NaN)
        """
        return talib.ATR(high, low, close, timeperiod=period)

    # ========================================
    # 기간 최고 종가 (Period High Close) 계산
    # ========================================

    def calculate_period_high(
        self,
        close_prices: np.ndarray,
        period: int,
    ) -> np.ndarray:
        """
        기간 내 최고 종가 계산 (당일 제외, 과거 N일 기준)
        
        백테스팅 시 Look-ahead bias 방지를 위해
        당일 종가는 제외하고 "과거 N일"의 최고 종가를 반환합니다.
        
        예: HIGH(20)의 경우
        - 오늘 날짜: t
        - 계산 대상: close[t-20] ~ close[t-1] 중 최댓값
        
        진입 조건: "오늘 종가 > HIGH(20)" → 20일 신고가 돌파

        Args:
            close_prices: 종가 배열 (오래된 날짜 → 최신 날짜 순서)
            period: 기간 (일)

        Returns:
            기간 최고 종가 배열 (앞부분은 NaN)
        """
        result = np.full(len(close_prices), np.nan)
        
        # period일 이후부터 계산 가능 (당일 제외이므로 period+1번째 데이터부터)
        for i in range(period, len(close_prices)):
            # 당일(i) 제외, 과거 period일간의 최고 종가
            result[i] = np.max(close_prices[i - period : i])
        
        return result

    # ========================================
    # RSI (Relative Strength Index) 계산
    # ========================================

    def calculate_rsi(
        self,
        close_prices: np.ndarray,
        period: int,
    ) -> np.ndarray:
        """
        RSI (상대강도지수) 계산

        Args:
            close_prices: 종가 배열
            period: 기간 (보통 14일)

        Returns:
            RSI 값 배열 (0~100)
        """
        return talib.RSI(close_prices, timeperiod=period)

    # ========================================
    # EMA 기울기 계산 (ATR 정규화)
    # ========================================

    def calculate_ema_slope(
        self,
        close_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        ema_period: int,
        atr_period: int = 20,
    ) -> np.ndarray:
        """
        EMA 기울기 계산 (ATR 정규화)
        
        구조 필터로 사용: EMA의 일일 변화량을 ATR로 나누어
        변동성에 따른 상대적 움직임을 측정합니다.
        
        계산식: slope = (EMA[today] - EMA[yesterday]) / ATR
        
        해석:
        - slope >= -0.2: 상승 또는 보합 (진입 허용)
        - slope < -0.2: 하락 추세 (진입 금지)
        - slope < -0.3: 강한 하락 (청산 조건)

        Args:
            close_prices: 종가 배열
            high_prices: 고가 배열
            low_prices: 저가 배열
            ema_period: EMA 기간 (예: 50)
            atr_period: ATR 기간 (기본 20)

        Returns:
            ATR 정규화된 EMA 기울기 배열
        """
        # EMA 계산
        ema = talib.EMA(close_prices, timeperiod=ema_period)
        
        # ATR 계산
        atr = talib.ATR(high_prices, low_prices, close_prices, timeperiod=atr_period)
        
        # 기울기 계산: (EMA[today] - EMA[yesterday]) / ATR
        slope = np.full(len(close_prices), np.nan)
        
        for i in range(1, len(close_prices)):
            if not np.isnan(ema[i]) and not np.isnan(ema[i-1]) and not np.isnan(atr[i]) and atr[i] > 0:
                slope[i] = (ema[i] - ema[i-1]) / atr[i]
        
        return slope

    # ========================================
    # 이동평균 스테이지 (EMA STAGE) 계산
    # ========================================

    def calculate_ema_stage(
        self,
        close_prices: np.ndarray,
    ) -> np.ndarray:
        """
        이동평균 스테이지 (1~6) 계산
        
        단기(5), 중기(20), 장기(40) EMA의 배열에 따라 스테이지 결정
        
        | 스테이지 | 명칭 | 배열 (위>아래) |
        |---|---|---|
        | 1 | 안정 상승기 | 단기 > 중기 > 장기 |
        | 2 | 하락 변화기1 | 중기 > 단기 > 장기 |
        | 3 | 하락 변화기2 | 중기 > 장기 > 단기 |
        | 4 | 안정 하락기 | 장기 > 중기 > 단기 |
        | 5 | 상승 변화기1 | 장기 > 단기 > 중기 |
        | 6 | 상승 변화기2 | 단기 > 장기 > 중기 |

        Args:
            close_prices: 종가 배열

        Returns:
            스테이지 값 배열 (1~6, 계산 불가 시 0 또는 NaN)
            여기서는 관례적으로 0을 반환하도록 설정 (DB 저장은 필터링됨)
        """
        short_period = self.EMA_STAGE_PARAMS["short"]
        medium_period = self.EMA_STAGE_PARAMS["medium"]
        long_period = self.EMA_STAGE_PARAMS["long"]
        
        # EMA 계산
        ema_short = talib.EMA(close_prices, timeperiod=short_period)
        ema_medium = talib.EMA(close_prices, timeperiod=medium_period)
        ema_long = talib.EMA(close_prices, timeperiod=long_period)
        
        stages = np.full(len(close_prices), np.nan)
        
        # 계산 가능한 시점부터 반복
        start_idx = long_period - 1
        
        for i in range(start_idx, len(close_prices)):
            s = ema_short[i]
            m = ema_medium[i]
            l = ema_long[i]
            
            if np.isnan(s) or np.isnan(m) or np.isnan(l):
                continue
                
            if s > m > l:
                stages[i] = 1
            elif m > s > l:
                stages[i] = 2
            elif m > l > s:
                stages[i] = 3
            elif l > m > s:
                stages[i] = 4
            elif l > s > m:
                stages[i] = 5
            elif s > l > m:
                stages[i] = 6
            else:
                # 이론상 6개 케이스 외에는 존재하지 않으나 (3개 값 상이할 경우)
                # 값이 같은 경우가 있을 수 있음. 이 경우 이전 스테이지 유지하거나 처리 필요
                # 여기서는 0으로 처리 (혹은 이전 값 유지)
                # 단순화를 위해 일단 0 처리 하되, 추후 보완 가능
                stages[i] = 0
                
        return stages

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
            일봉 DataFrame (date, open, high, low, close 컬럼 포함)
        """
        query = (
            supabase.table("daily_candles")
            .select("date, open, high, low, close")
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
            df["open"] = pd.to_numeric(df["open"], errors="coerce")
            df["high"] = pd.to_numeric(df["high"], errors="coerce")
            df["low"] = pd.to_numeric(df["low"], errors="coerce")
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

        print(f"Calculated {len(indicators)} MA/EMA records for {ticker}")
        return indicators

    def calculate_all_indicators_for_ticker(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """
        특정 종목의 모든 기술적 지표 계산 (MA + EMA + ATR + HIGH)
        
        추세추종 전략 백테스팅에 필요한 모든 지표를 한 번에 계산합니다.

        Args:
            ticker: 종목 코드
            start_date: 계산 시작일 (YYYY-MM-DD)
            end_date: 계산 종료일 (YYYY-MM-DD)

        Returns:
            계산된 지표 딕셔너리 리스트
        """
        print(f"[{datetime.now()}] Calculating all indicators for {ticker}...")

        # 1. 일봉 데이터 조회 (OHLC 전체)
        # 가장 긴 기간(240일)을 고려하여 충분한 과거 데이터 조회
        df = self.fetch_candles(ticker, start_date=None, end_date=end_date)

        if df.empty:
            print(f"No candle data found for {ticker}")
            return []

        # 최소 데이터 수 체크
        required_periods = max(
            self.SMA_PERIODS + self.EMA_PERIODS + self.ATR_PERIODS + self.HIGH_PERIODS + self.RSI_PERIODS
        )
        if len(df) < required_periods:
            print(
                f"Warning: Insufficient data for {ticker}: {len(df)} rows "
                f"(recommended: {required_periods}). Calculating available indicators."
            )

        # 2. numpy 배열로 변환
        dates = df["date"].values
        open_prices = df["open"].values.astype(np.float64)
        high_prices = df["high"].values.astype(np.float64)
        low_prices = df["low"].values.astype(np.float64)
        close_prices = df["close"].values.astype(np.float64)

        indicators = []

        # 3. SMA 계산
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

        # 4. EMA 계산
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

        # 5. ATR 계산 (추세추종 전략용)
        for period in self.ATR_PERIODS:
            atr_values = self.calculate_atr(high_prices, low_prices, close_prices, period)
            indicators.extend(
                self._build_indicator_records(
                    ticker=ticker,
                    dates=dates,
                    values=atr_values,
                    indicator_type="ATR",
                    params={"period": period},
                    start_date=start_date,
                )
            )

        # 6. 기간 최고 종가 계산 (추세추종 전략용 - 20일 신고가 돌파 신호)
        for period in self.HIGH_PERIODS:
            high_values = self.calculate_period_high(close_prices, period)
            indicators.extend(
                self._build_indicator_records(
                    ticker=ticker,
                    dates=dates,
                    values=high_values,
                    indicator_type="HIGH",
                    params={"period": period},
                    start_date=start_date,
                )
            )

        # 7. RSI 계산
        for period in self.RSI_PERIODS:
            rsi_values = self.calculate_rsi(close_prices, period)
            indicators.extend(
                self._build_indicator_records(
                    ticker=ticker,
                    dates=dates,
                    values=rsi_values,
                    indicator_type="RSI",
                    params={"period": period},
                    start_date=start_date,
                )
            )

        # 8. EMA 기울기 계산 (추세추종 전략용 - 구조 필터)
        for period in self.EMA_SLOPE_PERIODS:
            slope_values = self.calculate_ema_slope(
                close_prices, high_prices, low_prices, ema_period=period
            )
            indicators.extend(
                self._build_indicator_records(
                    ticker=ticker,
                    dates=dates,
                    values=slope_values,
                    indicator_type="EMA_SLOPE",
                    params={"period": period},
                    start_date=start_date,
                )
            )
            
        # 9. EMA STAGE 계산
        stage_values = self.calculate_ema_stage(close_prices)
        indicators.extend(
            self._build_indicator_records(
                ticker=ticker,
                dates=dates,
                values=stage_values,
                indicator_type="EMA_STAGE",
                params=self.EMA_STAGE_PARAMS,
                start_date=start_date,
            )
        )

        print(f"Calculated {len(indicators)} total indicator records for {ticker}")
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
                # 모든 기술적 지표 계산 (MA + EMA + ATR + HIGH)
                indicators = self.calculate_all_indicators_for_ticker(
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
