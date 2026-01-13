import FinanceDataReader as fdr
import pandas as pd

def probe_fdr():
    print("--- Probing FDR StockListing('KRX') ---")
    try:
        df = fdr.StockListing('KRX')
        print(f"Rows: {len(df)}")
        if not df.empty:
            print(f"Columns: {list(df.columns)}")
            print("First Row:")
            print(df.iloc[0])
            
            # Check Amount
            amount_cols = [c for c in df.columns if 'Amount' in c or '거래대금' in c]
            print(f"Amount Columns found: {amount_cols}")
            if amount_cols:
                print(f"Sample Amount: {df.iloc[0][amount_cols[0]]}")
    except Exception as e:
        print(f"FDR Error: {e}")

if __name__ == "__main__":
    probe_fdr()
