
import FinanceDataReader as fdr
import pandas as pd
import sys

print(f"Python Executable: {sys.executable}")
print(f"Pandas Version: {pd.__version__}")
try:
    print(f"FDR Version: {fdr.__version__}")
except:
    print("FDR version not found")

def check_fdr():
    print("\nfetching fdr.StockListing('KRX')...")
    df = fdr.StockListing('KRX')
    print(f"Total Rows: {len(df)}")
    
    # Group by Market
    if 'Market' in df.columns:
        print("\nMarket Counts:")
        print(df['Market'].value_counts())
    else:
        print("No 'Market' column found!")
        print(df.columns)

    # Check for ETFs/ETNs hints
    # Usually they don't have distinct Market in KRX listing, but let's see.
    # We can check Sector or Name
    
    # Check if 'Sector' exists (it might not in basic KRX list, only in KRX-DESC)
    if 'Sector' in df.columns:
        print("\nSector present. Null count:")
        print(df['Sector'].isnull().sum())
    else:
        print("\n'Sector' column not in basic listing (Expected).")

    # Let's count items that look like KOSPI/KOSDAQ but might be ETF
    filtered = df[df['Market'].isin(['KOSPI', 'KOSDAQ'])]
    print(f"\nFiltered (KOSPI+KOSDAQ): {len(filtered)}")

    # Check some tickers
    print("\nSample Tickers:")
    print(filtered[['Code', 'Name', 'Market']].head(10))

if __name__ == "__main__":
    check_fdr()
