
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.services.krx_collector import krx_collector
from app.db.client import supabase
import time

class HybridCollector:
    """
    FDR(수정주가 OHLCV)과 KRX(거래대금, 시가총액) 데이터를 병합하여 수집하는 수집기
    """
    
    def backfill_hybrid(self, start_date: str, end_date: str):
        """
        기간별 하이브리드 백필 실행
        메모리 효율을 위해 월 단위로 나누어 처리합니다.
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        current = start_dt
        while current <= end_dt:
            # 월 단위 청크 설정
            chunk_end = current + relativedelta(months=1) - relativedelta(days=1)
            if chunk_end > end_dt:
                chunk_end = end_dt
                
            s_str = current.strftime("%Y-%m-%d")
            e_str = chunk_end.strftime("%Y-%m-%d")
            
            print(f"\n>>> Processing Chunk: {s_str} ~ {e_str}")
            self._process_chunk(s_str, e_str)
            
            current = chunk_end + relativedelta(days=1)

    def _process_chunk(self, start_date: str, end_date: str):
        # 1. KRX 데이터 선수집 (Amount, MarketCap 확보)
        # map[ticker][date] = {amount, market_cap, open, high, low, close, volume, change_rate}
        print("  1. Pre-fetching KRX data (Amount/Cap)...")
        krx_map = self._fetch_krx_map(start_date, end_date)
        print(f"     -> Cached KRX data for {len(krx_map)} tickers.")
        
        # 2. 활성 종목 리스트 가져오기
        active_tickers = self._get_active_tickers()
        print(f"  2. Processing {len(active_tickers)} tickers with FDR...")
        
        # 3. 종목별 FDR 데이터 수집 및 병합
        total_upserted = 0
        
        for idx, ticker in enumerate(active_tickers):
            try:
                candles = []
                fdr_success = False

                # Try FDR first
                try:
                    df = fdr.DataReader(ticker, start_date, end_date)
                    if not df.empty:
                        fdr_success = True
                        for date_idx, row in df.iterrows():
                            date_str = date_idx.strftime("%Y-%m-%d")
                            
                            # KRX 데이터 조회 (없으면 0)
                            krx_info = krx_map.get(ticker, {}).get(date_str, {})
                            amount = krx_info.get('amount', 0)
                            market_cap = krx_info.get('market_cap', 0)
                            
                            # OHLCV 데이터 (FDR)
                            if pd.isna(row['Close']): continue
                            
                            candle = {
                                "ticker": ticker,
                                "date": date_str,
                                "open": int(row['Open']) if not pd.isna(row['Open']) else 0,
                                "high": int(row['High']) if not pd.isna(row['High']) else 0,
                                "low": int(row['Low']) if not pd.isna(row['Low']) else 0,
                                "close": int(row['Close']),
                                "volume": int(row['Volume']) if not pd.isna(row['Volume']) else 0,
                                "change_rate": float(row['Change']) * 100 if 'Change' in row and not pd.isna(row['Change']) else 0.0,
                                "amount": float(amount),       # From KRX
                                "market_cap": int(market_cap), # From KRX
                                "created_at": datetime.utcnow().isoformat()
                            }
                            candles.append(candle)
                except Exception as e:
                    # FDR Failure (404, etc) -> Proceed to Fallback
                    # print(f"     FDR Failed for {ticker}, trying fallback... ({e})")
                    fdr_success = False

                # Fallback to KRX if FDR failed or was empty
                if not fdr_success or not candles: 
                     # Check if we have KRX data for this ticker in the range
                     ticker_krx_data = krx_map.get(ticker, {})
                     if ticker_krx_data:
                         # Iterate dates in range
                         s_dt = datetime.strptime(start_date, "%Y-%m-%d")
                         e_dt = datetime.strptime(end_date, "%Y-%m-%d")
                         delta = e_dt - s_dt
                         
                         candles = [] # Reset to be safe, though likely empty
                         for i in range(delta.days + 1):
                             day = s_dt + relativedelta(days=i)
                             date_str = day.strftime("%Y-%m-%d")
                             
                             if date_str in ticker_krx_data:
                                 info = ticker_krx_data[date_str]
                                 # Use KRX data directly
                                 candle = {
                                     "ticker": ticker,
                                     "date": date_str,
                                     "open": info.get('open', 0),
                                     "high": info.get('high', 0),
                                     "low": info.get('low', 0),
                                     "close": info.get('close', 0),
                                     "volume": info.get('volume', 0),
                                     "change_rate": info.get('change_rate', 0.0),
                                     "amount": info.get('amount', 0),
                                     "market_cap": info.get('market_cap', 0),
                                     "created_at": datetime.utcnow().isoformat()
                                 }
                                 candles.append(candle)
                                 
                         if candles:
                             print(f"     [Fallback] Used KRX data for {ticker} ({len(candles)} rows)")

                # DB Upsert
                if candles:
                    supabase.table("daily_candles").upsert(candles, on_conflict="ticker, date").execute()
                    total_upserted += len(candles)
            
            except Exception as e:
                print(f"     Error processing {ticker}: {e}")
                
            # Progress Log
            if (idx + 1) % 100 == 0:
                print(f"     Processed {idx + 1}/{len(active_tickers)} tickers...")

        print(f"  [Chunk Done] Total upserted rows: {total_upserted}")


    def _fetch_krx_map(self, start_date: str, end_date: str) -> dict:
        """
        KRX API를 일자별로 호출하여 {ticker: {date: info}} 맵 생성
        """
        # krx_collector의 fetch_market_ohlcv_by_date 활용
        # 하지만 krx_collector는 리스트를 반환함. 이를 맵으로 변환 필요.
        
        # 날짜 루프
        s_dt = datetime.strptime(start_date, "%Y-%m-%d")
        e_dt = datetime.strptime(end_date, "%Y-%m-%d")
        delta = e_dt - s_dt
        
        result_map = {} # {ticker: {date: {amount, market_cap, ...}}}
        
        for i in range(delta.days + 1):
            day = s_dt + relativedelta(days=i)
            day_str_api = day.strftime("%Y%m%d") # API용
            day_str_db = day.strftime("%Y-%m-%d") # DB/Map용
            
            # 주말/공휴일 체크는 API 호출 실패로 자연스럽게 처리하거나, 여기서 평일 체크 가능
            if day.weekday() >= 5: continue # 주말 스킵
            
            try:
                # KRX 호출 (krx_collector 인스턴스 사용)
                # fetch_market_ohlcv_by_date는 로깅을 하므로 좀 시끄러울 수 있음.
                items = krx_collector.fetch_market_ohlcv_by_date(day_str_api)
                
                for item in items:
                    t = item['ticker']
                    if t not in result_map:
                        result_map[t] = {}
                        
                    result_map[t][day_str_db] = {
                        "amount": item['amount'],
                        "market_cap": item['market_cap'],
                        "open": item['open'],
                        "high": item['high'],
                        "low": item['low'],
                        "close": item['close'],
                        "volume": item['volume'],
                        "change_rate": item['change_rate']
                    }
                
                time.sleep(0.1) # Rate limit
                
            except Exception as e:
                print(f"     Error pre-fetching KRX for {day_str_db}: {e}")
                
        return result_map

    def _get_active_tickers(self):
        try:
            # 전체 종목 가져오기 (active only)
            # 페이징 필요
            all_tickers = []
            offset = 0
            limit = 1000
            while True:
                resp = supabase.table("stocks").select("ticker").eq("is_active", True).range(offset, offset+limit-1).execute()
                if not resp.data: break
                all_tickers.extend([x['ticker'] for x in resp.data])
                offset += limit
                if len(resp.data) < limit: break
            return all_tickers
        except Exception:
            return []

hybrid_collector = HybridCollector()
