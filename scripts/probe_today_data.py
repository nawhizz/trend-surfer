import FinanceDataReader as fdr
from pykrx import stock
import pandas as pd
from datetime import datetime

def probe_today():
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_compact = datetime.now().strftime("%Y%m%d")
    print(f"--- Probing Data for Today: {today_str} ---")

    # 1. FDR StockListing('KRX')
    print("\n[1] FDR StockListing('KRX')")
    try:
        df_fdr = fdr.StockListing('KRX')
        print(f"Rows: {len(df_fdr)}")
        if not df_fdr.empty:
            print(f"FDR Columns: {list(df_fdr.columns)}")
            sample = df_fdr.iloc[0]
            # Check common names for Amount
            amt = sample.get('Amount') or sample.get('거래대금')
            vol = sample.get('Volume') or sample.get('거래량')
            print(f"Sample (Code={sample.get('Code')}): Amount={amt}, Volume={vol}")
    except Exception as e:
        print(f"FDR Error: {e}")

    # 2. PyKRX get_market_ohlcv
    print(f"\n[2] PyKRX get_market_ohlcv({today_compact})")
    try:
        df_pykrx = stock.get_market_ohlcv(today_compact, market="ALL")
        print(f"Rows: {len(df_pykrx)}")
        if not df_pykrx.empty:
            print(f"Columns: {list(df_pykrx.columns)}")
            print("First row data:")
            print(df_pykrx.iloc[0])
        else:
            print("PyKRX returned empty dataframe.")
    except Exception as e:
        print(f"PyKRX Error: {e}")

if __name__ == "__main__":
    probe_today()
