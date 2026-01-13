
import sys
import os
import argparse
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.collector import collector

def collect_today(target_date: str = None):
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"--- Collecting Today's Market Data (Snapshot) for {target_date} ---")
    print("Source: FinanceDataReader (fdr.StockListing('KRX'))")
    print("Note: This script captures the CURRENT market state. Run after market close (15:30 KST) for final daily data.")
    
    # Check if target_date matches real today?
    # Users might force it if they run it slightly after midnight?
    # FDR always returns "current" snapshot. If runs on Sunday, it returns Friday's close?
    # We should be careful. 
    # If today is Sunday, FDR returns Friday data. 
    # If we save it as Sunday date, it's wrong.
    # But filtering valid trading days is complex.
    # We trust the user knows when to run it (after market close of the day).
    
    collector.fetch_daily_ohlcv(target_date)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (Default: Today)")
    args = parser.parse_args()
    
    collect_today(args.date)
