from pykrx import stock
import pandas as pd

def test_by_ticker():
    date = "20240103"
    print(f"Testing get_market_ohlcv_by_ticker for {date} with adjusted=True...")
    try:
        # Note: function name might be get_market_ohlcv_by_ticker
        # Docs say param is 'adjusted' for some funcs.
        df = stock.get_market_ohlcv_by_ticker(date, market="KOSPI", adjusted=True)
        print("Success!")
        print(df.head())
        
        print("\nChecking if values differ from unadjusted...")
        df_unadj = stock.get_market_ohlcv_by_ticker(date, market="KOSPI", adjusted=False)
        
        # Compare
        df['diff'] = df['종가'] - df_unadj['종가']
        diff_count = len(df[df['diff'] != 0])
        print(f"Tickers with diff: {diff_count}")
        
    except TypeError as e:
        print(f"TypeError: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_by_ticker()
