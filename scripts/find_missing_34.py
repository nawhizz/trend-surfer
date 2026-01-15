
import os
import sys
import pandas as pd
import FinanceDataReader as fdr
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app.db.client import supabase

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def find_missing_data_tickers():
    print("--- Identifying Active Tickers with Missing FDR Data ---")
    
    # 1. Active Tickers
    print("Fetching active tickers from DB...")
    active_tickers = []
    offset = 0
    limit = 1000
    while True:
        resp = supabase.table("stocks").select("ticker, name").eq("is_active", True).range(offset, offset+limit-1).execute()
        if not resp.data: break
        active_tickers.extend(resp.data)
        offset += limit
        if len(resp.data) < limit: break
            
    print(f"Total Active Tickers: {len(active_tickers)}")
    
    # 2. Test Range
    # Use a recent valid trading day. 2026-01-14 is Tuesday.
    start_date = "2026-01-14"
    end_date = "2026-01-14"
    print(f"Testing for date: {start_date}")

    failed_tickers = []
    
    # Optimizing: We can't batch call DataReader for KRX easily without loop or full Listing.
    # But wait, User said backfill (DataReader) missed 34.
    # We can try to reproduce by calling DataReader for each.
    
    # To speed up, maybe just check 1 day.
    
    count = 0
    for item in active_tickers:
        ticker = item['ticker']
        name = item['name']
        
        try:
            df = fdr.DataReader(ticker, start_date, end_date)
            if df.empty:
                failed_tickers.append(item)
                print(f"MISSING: {ticker} ({name}) - Empty DataFrame")
            else:
                 # Check if Close is 0 or NaN just in case
                 if pd.isna(df.iloc[0]['Close']) or df.iloc[0]['Close'] == 0:
                     # Some tickers might have 0 price? Unlikely for active.
                     pass
        except Exception as e:
            failed_tickers.append(item)
            print(f"ERROR: {ticker} ({name}) - {e}")
            
        count += 1
        if count % 100 == 0:
            print(f"Checked {count}/{len(active_tickers)}...")

    print(f"\n--- Result ---")
    print(f"Total Missing/Failed: {len(failed_tickers)}")
    print("\nList of Missing Tickers:")
    for t in failed_tickers:
        print(f"- {t['ticker']} : {t['name']}")

if __name__ == "__main__":
    find_missing_data_tickers()
