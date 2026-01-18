"""
시장 필터 서비스 (Market Regime Filter)

추세추종 전략의 시장 필터를 담당합니다.
KOSPI와 KOSDAQ 지수가 모두 60일 이동평균 위에 있을 때만 신규 진입을 허용합니다.

규칙:
    KOSPI 종가 > KOSPI 60MA AND KOSDAQ 종가 > KOSDAQ 60MA
"""

import json
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from app.db.client import supabase


# 시장 필터에 사용되는 지수
MARKET_INDICES = {
    "KS11": "KOSPI",
    "KQ11": "KOSDAQ",
}

# 시장 필터 MA 기간
MARKET_FILTER_MA_PERIOD = 60


class MarketFilter:
    """
    시장 필터 서비스
    
    KOSPI/KOSDAQ 지수의 60일 이동평균을 기준으로 시장 상태를 판단합니다.
    """

    def __init__(self):
        pass

    def _fetch_index_close(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        지수 종가 데이터 조회
        
        Args:
            ticker: 지수 코드 (KS11, KQ11)
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            
        Returns:
            DataFrame with columns: date, close
        """
        response = (
            supabase.table("daily_candles")
            .select("date, close")
            .eq("ticker", ticker)
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
            .execute()
        )

        if not response.data:
            return pd.DataFrame(columns=["date", "close"])

        df = pd.DataFrame(response.data)
        df["close"] = df["close"].astype(float)
        return df

    def _calculate_ma(self, close_prices: np.ndarray, period: int) -> np.ndarray:
        """
        단순이동평균 계산
        
        Args:
            close_prices: 종가 배열
            period: 이동평균 기간
            
        Returns:
            MA 값 배열 (앞부분은 NaN)
        """
        result = np.full(len(close_prices), np.nan)
        for i in range(period - 1, len(close_prices)):
            result[i] = np.mean(close_prices[i - period + 1 : i + 1])
        return result

    def get_index_ma(
        self,
        ticker: str,
        target_date: str,
        lookback_days: int = 120,
    ) -> Optional[float]:
        """
        특정 날짜의 지수 MA(60) 값 조회
        
        Args:
            ticker: 지수 코드 (KS11, KQ11)
            target_date: 조회 기준일 (YYYY-MM-DD)
            lookback_days: 조회할 과거 데이터 일수 (MA 계산에 충분한 기간)
            
        Returns:
            MA(60) 값, 계산 불가 시 None
        """
        # 충분한 데이터를 위해 과거 데이터 조회
        from datetime import timedelta

        end_dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days)
        start_date = start_dt.strftime("%Y-%m-%d")

        df = self._fetch_index_close(ticker, start_date, target_date)

        if df.empty or len(df) < MARKET_FILTER_MA_PERIOD:
            return None

        close_prices = df["close"].values
        ma_values = self._calculate_ma(close_prices, MARKET_FILTER_MA_PERIOD)

        # 마지막 유효한 MA 값 반환
        if not np.isnan(ma_values[-1]):
            return float(ma_values[-1])

        return None

    def get_index_close(
        self,
        ticker: str,
        target_date: str,
    ) -> Optional[float]:
        """
        특정 날짜의 지수 종가 조회
        
        Args:
            ticker: 지수 코드 (KS11, KQ11)
            target_date: 조회 기준일 (YYYY-MM-DD)
            
        Returns:
            종가, 데이터 없으면 None
        """
        response = (
            supabase.table("daily_candles")
            .select("close")
            .eq("ticker", ticker)
            .eq("date", target_date)
            .execute()
        )

        if response.data and len(response.data) > 0:
            return float(response.data[0]["close"])

        return None

    def get_market_status(self, date: str) -> dict:
        """
        특정 날짜의 시장 상태 상세 정보 반환
        
        Args:
            date: 기준일 (YYYY-MM-DD)
            
        Returns:
            시장 상태 정보 딕셔너리
        """
        result = {
            "date": date,
            "kospi_close": None,
            "kospi_ma60": None,
            "kospi_above_ma": None,
            "kosdaq_close": None,
            "kosdaq_ma60": None,
            "kosdaq_above_ma": None,
            "is_bullish": None,
        }

        # KOSPI (KS11)
        kospi_close = self.get_index_close("KS11", date)
        kospi_ma60 = self.get_index_ma("KS11", date)

        result["kospi_close"] = kospi_close
        result["kospi_ma60"] = round(kospi_ma60, 2) if kospi_ma60 else None
        if kospi_close is not None and kospi_ma60 is not None:
            result["kospi_above_ma"] = kospi_close > kospi_ma60

        # KOSDAQ (KQ11)
        kosdaq_close = self.get_index_close("KQ11", date)
        kosdaq_ma60 = self.get_index_ma("KQ11", date)

        result["kosdaq_close"] = kosdaq_close
        result["kosdaq_ma60"] = round(kosdaq_ma60, 2) if kosdaq_ma60 else None
        if kosdaq_close is not None and kosdaq_ma60 is not None:
            result["kosdaq_above_ma"] = kosdaq_close > kosdaq_ma60

        # 최종 판단: 둘 다 MA 위에 있어야 bullish
        if result["kospi_above_ma"] is not None and result["kosdaq_above_ma"] is not None:
            result["is_bullish"] = result["kospi_above_ma"] and result["kosdaq_above_ma"]

        return result

    def is_bullish(self, date: str) -> bool:
        """
        시장 필터 조건 확인
        
        Args:
            date: 기준일 (YYYY-MM-DD)
            
        Returns:
            True: KOSPI > MA60 AND KOSDAQ > MA60 (신규 진입 허용)
            False: 신규 진입 금지 또는 판단 불가
        """
        status = self.get_market_status(date)
        return status.get("is_bullish", False) is True

    def get_index_ema_slope(
        self,
        ticker: str,
        target_date: str,
    ) -> Optional[float]:
        """
        특정 날짜의 지수 EMA50 기울기 조회 (DB에서)
        
        Args:
            ticker: 지수 코드 (KS11, KQ11)
            target_date: 조회 기준일 (YYYY-MM-DD)
            
        Returns:
            EMA_SLOPE_50 값, 없으면 None
        """
        # EMA_SLOPE 지표 조회 (period 50)
        # indicator_type으로만 조회 (EMA_SLOPE_50은 유일하므로 params 필터 불필요)
        response = (
            supabase.table("daily_technical_indicators")
            .select("value")
            .eq("ticker", ticker)
            .eq("date", target_date)
            .eq("indicator_type", "EMA_SLOPE")
            .execute()
        )
        
        if response.data and len(response.data) > 0:
            return float(response.data[0]["value"])
        
        return None

    def is_index_structure_ok(
        self,
        date: str,
        slope_threshold: float = -0.2,
    ) -> bool:
        """
        지수 구조 붕괴 여부 확인 (EMA50 기울기 기반)
        
        추세추종 전략의 시장 필터로 사용:
        - KOSPI와 KOSDAQ 모두 EMA50 기울기가 threshold 이상이어야 진입 허용
        
        Args:
            date: 기준일 (YYYY-MM-DD)
            slope_threshold: 기울기 임계값 (기본 -0.2)
            
        Returns:
            True: 지수 구조 정상 (진입 허용)
            False: 지수 구조 붕괴 (진입 금지)
        """
        # KOSPI EMA50 기울기 확인
        kospi_slope = self.get_index_ema_slope("KS11", date)
        if kospi_slope is None or kospi_slope < slope_threshold:
            return False
        
        # KOSDAQ EMA50 기울기 확인
        kosdaq_slope = self.get_index_ema_slope("KQ11", date)
        if kosdaq_slope is None or kosdaq_slope < slope_threshold:
            return False
        
        return True

    def get_full_market_status(self, date: str) -> dict:
        """
        특정 날짜의 종합 시장 상태 조회 (MA60 + EMA50 기울기)
        
        Args:
            date: 기준일 (YYYY-MM-DD)
            
        Returns:
            종합 시장 상태 딕셔너리
        """
        # 기존 MA 기반 상태
        status = self.get_market_status(date)
        
        # EMA50 기울기 추가
        status["kospi_ema50_slope"] = self.get_index_ema_slope("KS11", date)
        status["kosdaq_ema50_slope"] = self.get_index_ema_slope("KQ11", date)
        
        # 구조 상태 추가
        status["is_structure_ok"] = self.is_index_structure_ok(date)
        
        return status

    def save_market_indicators_to_db(
        self,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> int:
        """
        지수의 MA(60) 지표를 DB에 저장
        
        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD), None이면 오늘
            
        Returns:
            저장된 레코드 수
        """
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")
        total_saved = 0

        for ticker in MARKET_INDICES.keys():
            print(f"  - {ticker} MA(60) 계산 중...")

            # 충분한 과거 데이터 조회 (MA 계산을 위해)
            from datetime import timedelta

            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            lookback_dt = start_dt - timedelta(days=MARKET_FILTER_MA_PERIOD * 2)
            lookback_start = lookback_dt.strftime("%Y-%m-%d")

            df = self._fetch_index_close(ticker, lookback_start, end_date)

            if df.empty or len(df) < MARKET_FILTER_MA_PERIOD:
                print(f"    ⚠ {ticker}: 데이터 부족 (len={len(df)})")
                continue

            # MA 계산
            close_prices = df["close"].values
            dates = df["date"].values
            ma_values = self._calculate_ma(close_prices, MARKET_FILTER_MA_PERIOD)

            # DB에 저장할 레코드 생성
            indicators = []
            for i, (d, ma) in enumerate(zip(dates, ma_values)):
                # start_date 이후의 유효한 값만 저장
                if d < start_date:
                    continue
                if np.isnan(ma):
                    continue

                indicator = {
                    "ticker": ticker,
                    "date": d,
                    "indicator_type": "MA",
                    "params": json.dumps({"period": MARKET_FILTER_MA_PERIOD}),
                    "value": float(ma),
                }
                indicators.append(indicator)

            # DB 저장 (배치)
            if indicators:
                chunk_size = 500
                for i in range(0, len(indicators), chunk_size):
                    chunk = indicators[i : i + chunk_size]
                    supabase.table("daily_technical_indicators").upsert(chunk).execute()
                print(f"    ✓ {ticker}: {len(indicators)} rows 저장 완료")
                total_saved += len(indicators)
            else:
                print(f"    ⚠ {ticker}: 저장할 지표 없음")

        return total_saved


# 싱글톤 인스턴스
market_filter = MarketFilter()
