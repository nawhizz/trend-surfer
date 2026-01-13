from pykrx import stock
import pandas as pd

target_date = "20240103" # Jan 3, 2024 (Definite trading day)

print(f"--- PyKRX Market-wide check for {target_date} (KOSPI) ---")
try:
    # get_market_ohlcv(date, market="...") returns snapshot of all stocks
    df = stock.get_market_ohlcv(target_date, market="KOSPI")
    print("Columns:", df.columns.tolist())
    if not df.empty:
        print("Sample Row (First):")
        print(df.iloc[0])
        
    if "거래대금" in df.columns:
        print(">>> FOUND '거래대금' (Amount)!")
    else:
        print(">>> '거래대금' NOT FOUND.")

except Exception as e:
    print("Error:", e)



