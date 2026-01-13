import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime

ticker = '005930' # Samsung Electronics
start_date = '2024-01-02'
end_date = '2024-01-05'

print(f"Fetching {ticker} from {start_date} to {end_date}...")
df = fdr.DataReader(ticker, start_date, end_date)
print("Columns:", df.columns)
print(df.head())

if 'Change' in df.columns:
    print("Change column exists")
else:
    print("Change column MISSING")
    
if 'Amount' in df.columns:
    print("Amount column exists")
else:
    print("Amount column MISSING (Approx via Close*Volume?)")
