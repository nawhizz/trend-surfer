
import os
import sys
import FinanceDataReader as fdr
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app.db.client import supabase

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def inspect_tickers(tickers):
    print("--- Inspecting Tickers in DB ---")
    try:
        response = supabase.table("stocks").select("*").in_("ticker", tickers).execute()
        for item in response.data:
            print(f"Ticker: {item['ticker']}, Name: {item['name']}, Market: {item.get('market', 'N/A')}, Sector: {item.get('sector', 'N/A')}, Code: {item.get('standard_code', 'N/A')}")
    except Exception as e:
        print(f"Error fetching from DB: {e}")

    print("\n--- Testing FDR with Tickers ---")
    for ticker in tickers:
        print(f"Testing {ticker} with FDR...")
        try:
            # Test typical date range
            df = fdr.DataReader(ticker, "2024-01-01", "2024-01-10")
            print(f"  Success! Shape: {df.shape}")
        except Exception as e:
            print(f"  Failed: {e}")

if __name__ == "__main__":
    tickers_to_check = ['0126Z0', '0009K0', '0120G0', '005930'] # Included Samsung for reference
    inspect_tickers(tickers_to_check)
