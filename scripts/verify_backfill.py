import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app.db.client import supabase
import pandas as pd
import argparse

def verify(date, ticker="005930"):
    print(f"Verifying data for Ticker: {ticker} on Date: {date}")
    try:
        response = supabase.table("daily_candles") \
            .select("*") \
            .eq("ticker", ticker) \
            .eq("date", date) \
            .execute()

        data = response.data
        if not data:
            print("No data found!")
        else:
            df = pd.DataFrame(data)
            print(df[['date', 'ticker', 'close', 'volume', 'amount']])
            
            # Simple integrity check
            row = df.iloc[0]
            if row['amount'] > 0 and row['volume'] > 0:
                print("Data Integrity: OK (Amount and Volume Present)")
                calc = row['close'] * row['volume']
                diff = row['amount'] - calc
                if diff != 0:
                     print(f"Note: Amount ({row['amount']}) != Close*Volume ({calc}). Difference: {diff}")
                     print("This indicates 'Amount' is likely the real Transaction Value from KRX.")
                else:
                     print("Note: Amount matches Close*Volume exactly.")
            else:
                print("Data Integrity: Warning (Zero Amount or Volume)")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2024-01-03", help="Date to check")
    parser.add_argument("--ticker", default="005930", help="Ticker to check")
    args = parser.parse_args()
    verify(args.date, args.ticker)
