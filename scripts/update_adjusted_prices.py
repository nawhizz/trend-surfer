import sys
import os
import argparse
from datetime import datetime, timedelta
import pandas as pd

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.krx_collector import krx_collector
from app.services.indicator_calculator import indicator_calculator
from app.db.client import supabase

def get_db_yesterday_closes(tickers):
    # Fetch latest available Close for list of tickers from DB
    # Optimized: We want the 'last recorded close' before Today.
    # But simply, let's just fetch the record for 'Yesterday' (target_date - 1 day)
    # If yesterday was holiday, this might be empty.
    # Ideally we compare with "Last Available Close" but that's complex query.
    # For now, let's assume we run this daily on trading days, so check Y-1 (or Friday).
    
    # Actually, we can just fetch *latest* record for each ticker?
    # No, we need Yesterday's specific close to compare with API's Implicit Yesterday.
    pass

def detect_and_update(target_date_str=None, threshold=0.05, backfill_start_date="2020-01-01"):
    if not target_date_str:
        target_date_str = datetime.now().strftime("%Y%m%d")
    
    # 1. Fetch Today's Market Data from KRX API
    print(f"Fetching KRX Market Data for {target_date_str} to detect adjustments...")
    today_candles = krx_collector.fetch_market_ohlcv_by_date(target_date_str)
    
    if not today_candles:
        print("No market data fetched. Exiting.")
        return

    print(f"Fetched {len(today_candles)} rows from API.")

    # 2. Key Tickers to Check
    # We only care about tickers that exist in our DB
    try:
        resp = supabase.table("stocks").select("ticker").execute()
        db_tickers = {item['ticker'] for item in resp.data}
    except Exception as e:
        print(f"Error fetching DB tickers: {e}")
        return

    # Filter API items to those in DB
    valid_items = [c for c in today_candles if c['ticker'] in db_tickers]
    print(f"Checking {len(valid_items)} tickers against DB...")

    # 3. Batch Query DB for 'Yesterday's Close'
    # Determine 'Yesterday' (Business Day) is hard without calendar.
    # But wait, KRX API 'CMPPREVDD_PRC' (Change Amount) is 'Today - Yesterday'.
    # So 'Implicit Yesterday' = Today Close - Change Amount.
    # We should look for a DB record that matches the date implied? 
    # OR, we simply find the "Most Recent Record in DB" for that ticker.
    # If the "Most Recent Record" date != Today, then it IS the previous close we should compare against.
    
    # But wait, if we run this script *after* daily batch, DB might already have Today?
    # No, this script is likely run *before* or *during* daily batch, or we check specifically previous day.
    
    # Let's assume we run this BEFORE adding Today's candle to DB.
    # So 'latest' in DB is Yesterday.
    
    # However, to be robust, let's fetch the latest close for each ticker from DB.
    # "SELECT ticker, close, date FROM daily_candles WHERE (ticker, date) IN (SELECT ticker, MAX(date) FROM daily_candles GROUP BY ticker)"
    # That query is heavy.
    
    # Better approach:
    # Just Assume we compare against specific Date if we know it?
    # Or, just fetch "Yesterday" relative to target_date.
    # If yesterday was holiday, we might miss it.
    
    # Let's use 'Implied Previous Close' calculated from API.
    # And we query DB for that specific Price? No.
    
    # Let's try to fetch "Yesterday" from DB.
    dt = datetime.strptime(target_date_str, "%Y%m%d")
    yesterday = dt - timedelta(days=1)
    if yesterday.weekday() == 6: yesterday -= timedelta(days=2) # Sun -> Fri
    elif yesterday.weekday() == 5: yesterday -= timedelta(days=1) # Sat -> Fri
    
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    print(f"Comparing against DB Date: {yesterday_str} (Assumed Previous Trading Day)")
    
    # Fetch DB prices for yesterday_str
    # Paginate if needed
    db_map = {}
    try:
        # 3000 rows is small enough for one select if max_rows allowed, otherwise paginate
        limit = 3000
        resp = supabase.table("daily_candles").select("ticker, close").eq("date", yesterday_str).execute()
        for row in resp.data:
            db_map[row['ticker']] = row['close']
    except Exception as e:
        print(f"Error fetching DB data: {e}")
    
    print(f"Found {len(db_map)} records in DB for {yesterday_str}")
    
    if len(db_map) == 0:
        print("No DB records found for yesterday. Cannot verify adjustments.")
        return

    # 4. Compare
    adjustment_candidates = []
    
    for item in valid_items:
        ticker = item['ticker']
        if ticker not in db_map:
            continue
            
        today_close = item['close']
        
        # Calculate Implied Prev Close
        # KRX 'change_rate' is also available but low precision?
        # Let's used derived logic if accurate Amount is not available.
        # Wait, krx_collector currently maps 'change_rate' (FLUC_RT).
        # It does NOT map 'CMPPREVDD_PRC'. We need to add that to KRXCollector? 
        # OR we just modify KRXCollector to return it.
        # ACTUALLY, I haven't modified KRXCollector to return CMPPREVDD_PRC yet.
        # I only modified backfill_period. 
        # I need to modify fetch_market_ohlcv_by_date to include 'change_amount' or return raw item?
        
        # Let's use Rate for now as fallback? 
        # Implied Prev = Today / (1 + Rate/100)
        # Example: 100 -> 110 (+10%). Prev = 110 / 1.1 = 100.
        # 1:5 Split: 50000 -> 10000. Rate is 0% (if base adjusted) or -80%?
        # KRX API usually reports Rate based on Adjusted Previous. 
        # So if Split happened, Today=10,000. Rate=0%. Implied Prev = 10,000.
        # DB Yesterday = 50,000.
        # Diff = 40,000. Mismatch!
        
        rate = item['change_rate']
        implied_prev = today_close / (1 + rate/100.0)
        
        actual_prev = db_map[ticker]
        
        if actual_prev == 0: continue
        
        diff_ratio = abs(implied_prev - actual_prev) / actual_prev
        
        if diff_ratio > threshold:
            print(f"[DETECTED] {ticker}: DB={actual_prev}, Implied={implied_prev:.2f} (Today={today_close}, Rate={rate}%) -> Diff: {diff_ratio*100:.1f}%")
            adjustment_candidates.append(ticker)
            
    # 5. Trigger Update
    if adjustment_candidates:
        print(f"Found {len(adjustment_candidates)} tickers requiring update.")
        
        # Backfill Range
        start_bf = backfill_start_date
        end_bf = yesterday_str
        
        print(f"Triggering Backfill for {start_bf} ~ {end_bf}")
        krx_collector.backfill_period(start_bf, end_bf, target_tickers=adjustment_candidates)
        
        # Recalculate Indicators
        print(f"Triggering Indicator Recalculation for {len(adjustment_candidates)} tickers...")
        indicator_calculator.calculate_and_save_for_all_tickers(
            start_date=start_bf,
            end_date=end_bf,
            ticker_list=adjustment_candidates
        )
        
    else:
        print("No adjustments detected.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target Date YYYYMMDD (default: today)")
    parser.add_argument("--threshold", type=float, default=0.20, help="Mismatch threshold (0.2 = 20%)") 
    parser.add_argument("--start_date", default="2020-01-01", help="Backfill start date YYYY-MM-DD (default: 2020-01-01)")
    # 20% threshold is safe to avoid noise, splits are usually 50%+. 
    # Dividend drop is small. We want to catch Split/Merger which are huge.
    args = parser.parse_args()
    
    detect_and_update(args.date, args.threshold, args.start_date)
