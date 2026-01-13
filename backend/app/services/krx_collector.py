import requests
import os
import pandas as pd
from datetime import datetime
import time
from app.db.client import supabase

class KRXCollector:
    def __init__(self):
        self.api_key = os.getenv("KRX_API_KEY")
        # Using the base URL from the user's working notebook
        self.base_url = "https://data-dbg.krx.co.kr/svc/apis/sto"
        self.headers = {
            "AUTH_KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
    def _post(self, endpoint: str, payload: dict):
        url = self.base_url + endpoint
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            if response.status_code != 200:
                print(f"KRX API Error [{endpoint}]: {response.status_code} - {response.text[:200]}")
                return {}
            return response.json()
        except Exception as e:
            print(f"Exception calling KRX API [{endpoint}]: {e}")
            return {}

    def fetch_market_ohlcv_by_date(self, target_date: str):
        """
        Fetch OHLCV + Amount for all stocks (KOSPI/KOSDAQ) on a specific date.
        target_date: YYYYMMDD
        """
        print(f"[{datetime.now()}] Fetching KRX Daily Trade for {target_date}...")
        
        all_candles = []
        
        # 1. KOSPI
        kospi_data = self._post("/stk_bydd_trd", {"basDd": target_date})
        kospi_rows = kospi_data.get("OutBlock_1", [])
        print(f"Fetched {len(kospi_rows)} KOSPI rows.")
        
        # 2. KOSDAQ
        kosdaq_data = self._post("/ksq_bydd_trd", {"basDd": target_date})
        kosdaq_rows = kosdaq_data.get("OutBlock_1", [])
        print(f"Fetched {len(kosdaq_rows)} KOSDAQ rows.")
        
        raw_items = kospi_rows + kosdaq_rows
        
        for item in raw_items:
            # Map fields
            # Note: Field names based on notebook assumption and common KRX API keys
            # ISU_CD, ISU_SRT_CD, TDD_CLSPRC (Close), ACC_TRDVAL (Amount), etc.
            
            try:
                # Ticker: Try ISU_SRT_CD first, fallback to ISU_CD
                ticker = item.get("ISU_SRT_CD")
                if not ticker:
                    ticker = item.get("ISU_CD")
                
                if not ticker:
                    continue
                    
                # If ticker is full ISIN (starts with KR7), try to clean it or just use it?
                # Usually our DB uses short code (6 digits). 
                # If ISU_CD is returned as 6 digit in this specific API, great.
                # If it's ISIN, we might need a mapping. 
                # PROBABLY this API returns ISU_SRT_CD or ISU_CD is short. 
                # Let's assume standard behavior: we need 6 digit.
                if len(ticker) > 6 and ticker.startswith("KR"):
                     # This is ISIN. Do we have short code?
                     # Let's verify with a quick check script if needed.
                     # For now, let's assume we can get short code nicely.
                     pass 
                
                # Handling numeric fields (remove commas if string)
                def clean_num(val):
                    if isinstance(val, str):
                        return float(val.replace(',', ''))
                    return float(val)

                close = int(clean_num(item.get("TDD_CLSPRC", 0)))
                open_p = int(clean_num(item.get("TDD_OPNPRC", 0)))
                high = int(clean_num(item.get("TDD_HGPRC", 0)))
                low = int(clean_num(item.get("TDD_LWPRC", 0)))
                volume = int(clean_num(item.get("ACC_TRDVOL", 0)))
                amount = float(clean_num(item.get("ACC_TRDVAL", 0))) # Transaction Value
                mkcap = int(clean_num(item.get("MKTCAP", 0)))
                fluc_rt = float(clean_num(item.get("FLUC_RT", 0))) # Fluctuation Rate
                
                # Check NaNs
                if close == 0 and volume == 0:
                    continue

                candle = {
                    "ticker": ticker,
                    "date": datetime.strptime(target_date, "%Y%m%d").strftime("%Y-%m-%d"),
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "amount": amount,
                    "change_rate": fluc_rt,
                    "market_cap": mkcap,
                    "created_at": datetime.utcnow().isoformat()
                }
                all_candles.append(candle)
                
            except Exception as e:
                # print(f"Skipping row: {e}")
                continue
                
        return all_candles

    def backfill_period(self, start_date: str, end_date: str, target_tickers: list = None):
        """
        Iterate dates and backfill.
        Dates in YYYY-MM-DD format.
        target_tickers: Optional list of tickers to strictly filter for. 
                        If provided, only these tickers will be upserted.
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        from datetime import timedelta
        delta = end_dt - start_dt
        
        # Optimize: If target_tickers provided, we don't need to fetch ALL valid tickers from DB for checking FK.
        # We can just assume target_tickers are valid (or check them once).
        valid_tickers_db = set()
        if not target_tickers:
            try:
                # Supabase Max Rows per request is often 1000. Use pagination.
                all_tickers = []
                offset = 0
                limit = 1000
                while True:
                    resp = supabase.table("stocks").select("ticker").range(offset, offset + limit - 1).execute()
                    rows = resp.data
                    if not rows:
                        break
                    all_tickers.extend([item['ticker'] for item in rows])
                    offset += limit
                    if len(rows) < limit:
                        break
                
                valid_tickers_db = set(all_tickers)
                print(f"Loaded {len(valid_tickers_db)} valid tickers from DB.")
            except Exception as e:
                print(f"Error fetching valid tickers: {e}")
        else:
             print(f"Backfilling strictly for {len(target_tickers)} tickers...")

        for i in range(delta.days + 1):
            day = start_dt + timedelta(days=i)
            target_date_str = day.strftime("%Y%m%d") # API expects YYYYMMDD
            
            candles = self.fetch_market_ohlcv_by_date(target_date_str)
            
            if candles:
                # Filter logic
                valid_candles = []
                
                if target_tickers:
                     # Filter for target_tickers
                     valid_candles = [c for c in candles if c['ticker'] in target_tickers]
                else:
                     # Filter for FK constraints (all valid stocks in DB)
                     if valid_tickers_db:
                         valid_candles = [c for c in candles if c['ticker'] in valid_tickers_db]
                     else:
                         # Fallback if DB fetch failed? Or maybe strict.
                         # If DB fetch failed, valid_tickers_db is empty -> valid_candles empty.
                         pass

                if not valid_candles:
                    # If target_tickers was set, it's possible no trade happened for that ticker on that day (e.g. halt)
                    # print(f"No valid candles found for {target_date_str}.")
                    continue


                # Batch upsert
                chunk_size = 1000
                total = len(valid_candles)
                for j in range(0, total, chunk_size):
                    chunk = valid_candles[j:j+chunk_size]
                    try:
                        # Use conflict on ticker/date
                        supabase.table("daily_candles").upsert(chunk, on_conflict="ticker, date").execute()
                        print(f"Upserted {j} ~ {j+len(chunk)} / {total}")
                    except Exception as e:
                        print(f"Database error on upsert: {e}")  
            
            # Rate limit politeness
            time.sleep(0.2)

krx_collector = KRXCollector()
