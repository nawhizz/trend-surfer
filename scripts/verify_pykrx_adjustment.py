from pykrx import stock
import pandas as pd
from datetime import datetime, timedelta

def verify_adjustment_logic():
    # Target Date: Yesterday (or a recent trading day)
    # Ideally, we need a date where we know a split happened, or just scan for ANY difference.
    # Let's verify "Yesterday" or "Last Friday"
    
    today = datetime.now()
    # Find last business day
    offset = 1
    if today.weekday() == 0: offset = 3 # Mon -> Fri
    elif today.weekday() == 6: offset = 2 # Sun -> Fri
    
    target_date = (today - timedelta(days=offset)).strftime("%Y%m%d")
    print(f"Checking for adjustments on: {target_date}")

    print("Fetching Unadjusted Data...")
    df_raw = stock.get_market_ohlcv(target_date, market="ALL", adjusted=False)
    
    print("Fetching Adjusted Data...")
    df_adj = stock.get_market_ohlcv(target_date, market="ALL", adjusted=True)
    
    # Compare
    # Join on index (Ticker)
    comparison = df_raw[['종가']].join(df_adj[['종가']], lsuffix='_raw', rsuffix='_adj')
    
    # Calculate difference
    comparison['diff'] = comparison['종가_adj'] - comparison['종가_raw']
    
    # Filter where diff is not 0
    diff_df = comparison[comparison['diff'] != 0]
    
    print(f"Total Tickers: {len(comparison)}")
    print(f"Tickers with Adjusted Price mismatch: {len(diff_df)}")
    
    if len(diff_df) > 0:
        print("Sample Differences:")
        print(diff_df.head())
        # Check if difference implies split? 
        # Usually split reduces price significantly in raw vs adjusted if we look continuously.
        # Wait, get_market_ohlcv for ONE day:
        # If I get 2024-01-01 data NOW (2025):
        # Raw: 100,000 (Historical real price)
        # Adjusted: 20,000 (If split 1:5 happened in 2024-06)
        # So YES, fetching PAST data with adjusted=True vs False reveals if an event happened AFTER that date.
        
        print("\nLogic Verification: SUCCESS. Differences detected implies subsequent events.")
    else:
        print("\nNo differences found. (Maybe no events recently or PyKRX default behavior needs checking)")

if __name__ == "__main__":
    verify_adjustment_logic()
