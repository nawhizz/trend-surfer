
import os
import sys
import pandas as pd
import FinanceDataReader as fdr
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app.db.client import supabase

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def analyze_discrepancy():
    print("--- Analyzing Ticker Discrepancy ---")
    
    # 1. Get DB Active Tickers
    print("Fetching active tickers from DB...")
    db_tickers = set()
    db_market_counts = {}
    
    try:
        # Fetch all (pagination)
        all_rows = []
        offset = 0
        limit = 1000
        while True:
            resp = supabase.table("stocks").select("ticker, market").eq("is_active", True).range(offset, offset+limit-1).execute()
            if not resp.data: break
            all_rows.extend(resp.data)
            offset += limit
            if len(resp.data) < limit: break
            
        for row in all_rows:
            t = row['ticker']
            m = row['market']
            db_tickers.add(t)
            db_market_counts[m] = db_market_counts.get(m, 0) + 1
            
        print(f"DB Active Tickers: {len(db_tickers)}")
        print(f"DB Market Breakdown: {db_market_counts}")
        
    except Exception as e:
        print(f"Error fetching DB: {e}")
        return

    # 2. Get FDR Current Tickers
    print("\nFetching current tickers from FDR (KRX)...")
    try:
        df = fdr.StockListing('KRX')
        
        # Filter logic same as collect_today / collector
        fdr_tickers = set()
        fdr_market_counts = {}
        
        for idx, row in df.iterrows():
            market = row['Market']
            # We track raw market counts first
            fdr_market_counts[market] = fdr_market_counts.get(market, 0) + 1
            
            # Apply Filter
            if market not in ['KOSPI', 'KOSDAQ']:
                continue
            
            # Additional Filter from collector: Close/Vol check (optional, but collector does it)
            # collect_today logic:
            # if (pd.isna(close_val) or close_val == 0) and (pd.isna(vol_val) or vol_val == 0): continue
            
            ticker = str(row['Code'])
            fdr_tickers.add(ticker)
            
        print(f"FDR Raw Count: {len(df)}")
        print(f"FDR Market Breakdown (Raw): {fdr_market_counts}")
        print(f"FDR Filtered (KOSPI/KOSDAQ only) Count: {len(fdr_tickers)}")
        
    except Exception as e:
        print(f"Error fetching FDR: {e}")
        return

    # 3. Compare
    print("\n--- Comparison ---")
    only_in_db = db_tickers - fdr_tickers
    only_in_fdr = fdr_tickers - db_tickers
    
    print(f"Only in DB (Potential Zombies): {len(only_in_db)}")
    print(f"Only in FDR (New/Missing in DB): {len(only_in_fdr)}")
    
    if only_in_db:
        print("\nSample 'Only in DB' tickers:")
        # Check their markets in DB
        sample = list(only_in_db)[:10]
        resp = supabase.table("stocks").select("ticker, name, market").in_("ticker", sample).execute()
        for r in resp.data:
            print(r)

    if only_in_fdr:
        print("\nSample 'Only in FDR' tickers:")
        print(list(only_in_fdr)[:10])

if __name__ == "__main__":
    analyze_discrepancy()
