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
            # KRX returns both KOSPI and KOSDAQ with price info
            df = fdr.StockListing('KRX')
            print(f"Fetched {len(df)} tickers from KRX")

            # KRX-DESC contains detailed Sector info
            try:
                df_desc = fdr.StockListing('KRX-DESC')
                print(f"Fetched {len(df_desc)} tickers from KRX-DESC for Sector info")
                # Create a map: Code -> {Sector, Industry}
                # Use to_dict('index') matches index to row dict
                desc_map = df_desc.set_index('Code')[['Sector', 'Industry']].to_dict('index')
                print(f"Desc Map Size: {len(desc_map)}")
                if desc_map:
                     first_key = list(desc_map.keys())[0]
                     print(f"Sample Desc Key: {first_key}, Value: {desc_map[first_key]}")
            except Exception as e:
                print(f"Warning: Could not fetch KRX-DESC: {e}")
                desc_map = {}
            
            all_stocks = []
            
            # DataFrame columns: Code, Name, Market, Dept, Close, ...
            for index, row in df.iterrows():
                market = row['Market']
                if market not in ['KOSPI', 'KOSDAQ']:
                    continue

                ticker = str(row['Code'])
                
                # Preferred Stock Logic
                is_preferred = not ticker.endswith('0')
                
                # Sector & Industry Logic: Use KRX-DESC if available
                desc_info = desc_map.get(ticker, {})
                sector = desc_info.get('Sector')
                industry = desc_info.get('Industry')
                
                # Handle NaN
                if pd.isna(sector): sector = None
                if pd.isna(industry): industry = None

                # Fallback for sector from 'Dept'
                if not sector and 'Dept' in row:
                     dept = row['Dept']
                     if not pd.isna(dept):
                         sector = dept

                stock_data = {
                    "ticker": ticker, 
                    "name": row['Name'],
                    "market": market,
                    "sector": sector,
                    "industry": industry,
                    "is_preferred": is_preferred,
                    # "is_active": True, # Removed simplistic assumption if needed, but let's keep True for now
                    "is_active": not (pd.isna(row['Close']) or row['Close'] == 0), # Simple active check
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

                # FDR columns: Close, Open, High, Low, Volume, Change (Ratio?), Marcap...
                # Note: fdr.StockListing('KRX') columns are: 
                # Code, ISU_CD, Name, Market, Dept, Close, ChangeCode, Changes, ChagesRatio, Open, High, Low, Volume, Amount, Marcap, Stocks, MarketId
                
                candle = {
                    "ticker": str(row['Code']),
                    "date": target_date, # FDR Listing doesn't return date column, assume request date
                    "open": int(row['Open']),
                    "high": int(row['High']),
                    "low": int(row['Low']),
                    "close": int(row['Close']),
                    "volume": int(row['Volume']),
                    "amount": float(row['Amount']) if 'Amount' in row else 0,
                    "change_rate": float(row['ChagesRatio']) if 'ChagesRatio' in row and not pd.isna(row['ChagesRatio']) else 0,
                    "market_cap": int(row['Marcap']) if 'Marcap' in row and not pd.isna(row['Marcap']) else 0,
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
