from datetime import datetime
import pandas as pd
import FinanceDataReader as fdr
from app.db.client import supabase

class StockCollector:
    def __init__(self):
        pass

    def update_stock_list(self):
        """
        [FDR] 전 종목 목록(Ticker, Name)을 최신화합니다.
        fdr.StockListing('KRX') 사용
        """
        print(f"[{datetime.now()}] Starting Stock List Update (FDR)...")
        
        try:
            # KRX returns both KOSPI and KOSDAQ
            df = fdr.StockListing('KRX')
            print(f"Fetched {len(df)} tickers from KRX")
            
            all_stocks = []
            
            # DataFrame columns: Code, Name, Market, Dept, Close, ...
            for index, row in df.iterrows():
                market = row['Market']
                if market not in ['KOSPI', 'KOSDAQ']:
                    # Filter only KOSPI/KOSDAQ (ignore KONEX etc if needed, but TRD says KOSPI/KOSDAQ)
                    # FDR 'Market' column usually has KOSPI, KOSDAQ, KONEX
                    if market not in ['KOSPI', 'KOSDAQ']:
                        continue

                ticker = str(row['Code'])
                
                # Preferred Stock Logic: 
                # If ticker ends with '0', it's usually a Common Stock.
                # If it ends with non-zero (e.g., '5', '7', 'K', etc.), it's a Preferred Stock.
                is_preferred = not ticker.endswith('0')

                stock_data = {
                    "ticker": ticker, 
                    "name": row['Name'],
                    "market": market,
                    "sector": row['Dept'] if 'Dept' in row else None,
                    "is_preferred": is_preferred,
                    "is_active": True,
                    "updated_at": datetime.utcnow().isoformat()
                }
                all_stocks.append(stock_data)
            
            # Batch Upsert
            if all_stocks:
                chunk_size = 1000
                for i in range(0, len(all_stocks), chunk_size):
                    chunk = all_stocks[i:i + chunk_size]
                    supabase.table("stocks").upsert(chunk).execute()
                    print(f"Upserted stocks {i} to {i+len(chunk)}")
                print("Stock list updated successfully.")
            else:
                print("No stocks found to update.")

        except Exception as e:
            print(f"Error updating stock list with FDR: {e}")

    def fetch_daily_ohlcv(self, date_str: str = None):
        """
        [FDR] 전 종목의 일봉 데이터를 수집합니다.
        FDR의 StockListing('KRX')는 '현재(오늘)' 기준 전 종목 시세를 제공합니다.
        과거 데이터 Bulk 수집은 FDR로 어려우므로, 이 함수는 '오늘/최근' 데이터 수집용으로 사용합니다.
        특정 과거 날짜 수집이 필요하면 loop를 돌거나 다른 방법을 써야 하지만, 
        자동매매 시스템은 주로 '오늘' 데이터를 마감 후 수집하는게 핵심입니다.
        """
        target_date = date_str
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        # Note: fdr.StockListing acts on 'latest' available data. 
        # We assume the user calls this after market close to get 'today's' data.
        # If date_str is provided and is NOT today, FDR StockListing cannot fetch it easily in bulk.
        # ideally we should check if date_str matches today, otherwise warn.
        
        print(f"[{datetime.now()}] Starting Daily Candle Collection (FDR-StockListing) for {target_date}...")

        try:
            df = fdr.StockListing('KRX')
            
            all_candles = []
            
            for index, row in df.iterrows():
                # Filter Market
                market = row['Market']
                if market not in ['KOSPI', 'KOSDAQ']:
                    continue

                # Data validation (handling NaNs or zeros)
                if pd.isna(row['Open']) or row['Volume'] == 0:
                    continue

                candle = {
                    "ticker": str(row['Code']),
                    "date": target_date, # FDR Listing doesn't return date column, assume request date
                    "open": int(row['Open']),
                    "high": int(row['High']),
                    "low": int(row['Low']),
                    "close": int(row['Close']),
                    "volume": int(row['Volume']),
                    "amount": float(row['Amount']) if 'Amount' in row else 0,
                    "created_at": datetime.utcnow().isoformat()
                }
                all_candles.append(candle)
            
            # Batch Insert
            if all_candles:
                chunk_size = 1000
                for i in range(0, len(all_candles), chunk_size):
                    chunk = all_candles[i:i + chunk_size]
                    supabase.table("daily_candles").upsert(chunk).execute()
                    print(f"Inserted candles {i} to {i+len(chunk)}")
                print(f"Daily candles updated successfully for {target_date}.")
            else:
                print("No candles to insert.")

        except Exception as e:
            print(f"Error updating daily candles: {e}")

collector = StockCollector()
