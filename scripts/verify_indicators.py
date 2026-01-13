"""
이동평균 지표 백필 결과 상세 검증
- 처리된 종목 수 vs 전체 활성 종목 수 비교
- 지표별 건수 확인
"""

import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.db.client import supabase
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)


def main():
    print("=" * 60)
    print("이동평균 지표 백필 결과 검증")
    print("=" * 60)

    # 1. 활성 종목 수 (stocks 테이블)
    print("\n[1] 활성 종목 수 (stocks 테이블, is_active=True)")
    try:
        resp = supabase.table("stocks").select("count", count="exact").eq("is_active", True).execute()
        active_stock_count = resp.count
        print(f"    → {active_stock_count} 종목")
    except Exception as e:
        print(f"    Error: {e}")
        active_stock_count = 0

    # 2. 지표 테이블 전체 레코드 수
    print("\n[2] daily_technical_indicators 총 레코드 수")
    try:
        resp = supabase.table("daily_technical_indicators").select("count", count="exact").execute()
        total_indicator_count = resp.count
        print(f"    → {total_indicator_count} 건")
    except Exception as e:
        print(f"    Error: {e}")
        total_indicator_count = 0

    # 3. 지표 테이블의 고유 종목 수
    print("\n[3] daily_technical_indicators 고유 종목(ticker) 수")
    try:
        # Supabase에서 distinct count는 직접 지원하지 않으므로 
        # 전체 ticker를 가져와서 unique count 계산
        all_tickers = set()
        offset = 0
        limit = 1000
        
        while True:
            resp = supabase.table("daily_technical_indicators")\
                .select("ticker")\
                .range(offset, offset + limit - 1)\
                .execute()
            
            if not resp.data:
                break
                
            for row in resp.data:
                all_tickers.add(row['ticker'])
            
            offset += limit
            
            if len(resp.data) < limit:
                break
        
        unique_ticker_count = len(all_tickers)
        print(f"    → {unique_ticker_count} 종목")
        
        # 처리율 계산
        if active_stock_count > 0:
            coverage = (unique_ticker_count / active_stock_count) * 100
            print(f"    → 처리율: {coverage:.1f}% ({unique_ticker_count}/{active_stock_count})")
            
    except Exception as e:
        print(f"    Error: {e}")
        unique_ticker_count = 0

    # 4. 지표 유형별 레코드 수
    print("\n[4] 지표 유형별 레코드 수")
    indicator_types = ["MA", "EMA"]
    
    for ind_type in indicator_types:
        try:
            resp = supabase.table("daily_technical_indicators")\
                .select("count", count="exact")\
                .eq("indicator_type", ind_type)\
                .execute()
            print(f"    {ind_type}: {resp.count} 건")
        except Exception as e:
            print(f"    {ind_type}: Error - {e}")

    # 5. 일자별 레코드 수 (최근 5일)
    print("\n[5] 최근 일자별 레코드 수 (상위 5일)")
    try:
        # 최근 날짜 조회
        resp = supabase.table("daily_technical_indicators")\
            .select("date")\
            .order("date", desc=True)\
            .limit(1)\
            .execute()
        
        if resp.data:
            latest_date = resp.data[0]['date']
            print(f"    최신 날짜: {latest_date}")
            
            # 최근 5일 데이터 조회
            from datetime import datetime, timedelta
            latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
            
            for i in range(5):
                check_date = (latest_dt - timedelta(days=i)).strftime("%Y-%m-%d")
                resp = supabase.table("daily_technical_indicators")\
                    .select("count", count="exact")\
                    .eq("date", check_date)\
                    .execute()
                print(f"    {check_date}: {resp.count} 건")
        else:
            print("    데이터 없음")
            
    except Exception as e:
        print(f"    Error: {e}")

    # 6. 누락 종목 샘플 (처리되지 않은 종목)
    if active_stock_count > unique_ticker_count and unique_ticker_count > 0:
        print(f"\n[6] 누락 종목 샘플 (처리되지 않은 종목 중 5개)")
        try:
            # 활성 종목 리스트 가져오기
            resp = supabase.table("stocks").select("ticker").eq("is_active", True).limit(100).execute()
            active_tickers = set([row['ticker'] for row in resp.data])
            
            # 누락된 종목 찾기
            missing = active_tickers - all_tickers
            missing_sample = list(missing)[:5]
            
            for ticker in missing_sample:
                print(f"    - {ticker}")
                
            print(f"    ... 총 {len(missing)} 종목 누락")
        except Exception as e:
            print(f"    Error: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
