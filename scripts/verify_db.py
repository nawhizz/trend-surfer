from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load env from backend/.env (assuming script run from project root or similar, but let's be safe)
# Actually, loading from explicit path is better
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: Could not load SUPABASE_URL or SUPABASE_KEY from backend/.env")
    exit(1)

supabase: Client = create_client(url, key)

def verify_data():
    print("Verifying Supabase Tables...")
    
    # Check Stocks
    try:
        response = supabase.table("stocks").select("*", count="exact").limit(1).execute()
        count = response.count
        print(f"Stocks Table Count: {count}")
    except Exception as e:
        print(f"Error checking stocks: {e}")

    # Check Specific Stock Sector & Industry
    try:
        response = supabase.table("stocks").select("ticker, name, sector, industry").eq("ticker", "005930").execute()
        if response.data:
            print(f"Samsung Elec Info: {response.data[0]}")
    except Exception as e:
        print(f"Error checking sector/industry: {e}")

    # Check Daily Candles
    try:
        # Check for today's data (or latest)
        response = supabase.table("daily_candles").select("ticker, date, close, change_rate, market_cap").order("date", desc=True).limit(1).execute()
        if response.data:
            print(f"Latest Candle: {response.data[0]}")
        else:
            print("No candles found.")
            
        response = supabase.table("daily_candles").select("*", count="exact").limit(1).execute()
        count = response.count
        print(f"Daily Candles Table Count: {count}")
    except Exception as e:
        print(f"Error checking daily_candles: {e}")

if __name__ == "__main__":
    verify_data()
