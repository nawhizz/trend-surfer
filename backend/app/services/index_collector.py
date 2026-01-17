"""
지수 데이터 수집기 (Index Collector)

KOSPI와 KOSDAQ 지수의 일봉 데이터를 수집합니다.
시장 필터(Market Regime Filter) 판단에 사용됩니다.

지원 지수:
- KS11: KOSPI 지수
- KQ11: KOSDAQ 지수
"""

from datetime import datetime
from typing import Optional

import pandas as pd
import FinanceDataReader as fdr

from app.db.client import supabase


# 지수 심볼 정의
INDEX_SYMBOLS = {
    "KS11": {"name": "KOSPI 지수", "market": "INDEX"},
    "KQ11": {"name": "KOSDAQ 지수", "market": "INDEX"},
}


class IndexCollector:
    """
    지수 데이터 수집기
    
    FDR을 사용하여 KOSPI/KOSDAQ 지수 데이터를 수집하고 DB에 저장합니다.
    """

    def __init__(self):
        pass

    def ensure_index_masters(self):
        """
        지수 마스터 데이터가 stocks 테이블에 존재하는지 확인하고 없으면 추가
        """
        print(f"[{datetime.now()}] 지수 마스터 데이터 확인 및 추가...")

        for ticker, info in INDEX_SYMBOLS.items():
            stock_data = {
                "ticker": ticker,
                "name": info["name"],
                "market": info["market"],
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat(),
            }
            # upsert로 있으면 업데이트, 없으면 삽입
            supabase.table("stocks").upsert(stock_data).execute()
            print(f"  - {ticker} ({info['name']}) 확인 완료")

        print("지수 마스터 데이터 준비 완료")

    def fetch_index_candles(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        ticker: Optional[str] = None,
    ):
        """
        지수 일봉 데이터 수집 및 DB 저장
        
        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD), None이면 오늘까지
            ticker: 특정 지수만 수집 ('KS11' 또는 'KQ11'), None이면 모두 수집
        """
        # 마스터 데이터 확인
        self.ensure_index_masters()

        target_symbols = [ticker] if ticker else list(INDEX_SYMBOLS.keys())
        end_date = end_date or datetime.now().strftime("%Y-%m-%d")

        print(f"[{datetime.now()}] 지수 데이터 수집 ({start_date} ~ {end_date})...")

        for symbol in target_symbols:
            try:
                print(f"  - {symbol} 수집 중...")

                # FDR로 지수 데이터 조회
                df = fdr.DataReader(symbol, start_date, end_date)

                if df.empty:
                    print(f"    ⚠ {symbol}: 데이터 없음")
                    continue

                candles = []
                for date_idx, row in df.iterrows():
                    # 유효성 검사
                    if pd.isna(row["Open"]) or pd.isna(row["Close"]):
                        continue

                    # 등락률 계산 (FDR Change는 비율, 0.01 = 1%)
                    change_rate = 0.0
                    if "Change" in row and not pd.isna(row["Change"]):
                        change_rate = float(row["Change"]) * 100

                    candle = {
                        "ticker": symbol,
                        "date": date_idx.strftime("%Y-%m-%d"),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                        "amount": 0,  # 지수는 거래대금 없음
                        "change_rate": change_rate,
                        "market_cap": 0,  # 지수는 시가총액 없음
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    candles.append(candle)

                # DB 저장
                if candles:
                    supabase.table("daily_candles").upsert(candles).execute()
                    print(f"    ✓ {symbol}: {len(candles)} rows 저장 완료")
                else:
                    print(f"    ⚠ {symbol}: 유효 데이터 없음")

            except Exception as e:
                print(f"    ✗ {symbol} 오류: {e}")

        print("지수 데이터 수집 완료")


# 싱글톤 인스턴스
index_collector = IndexCollector()
