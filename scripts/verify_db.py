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

    # Check Daily Candles
    try:
        response = supabase.table("daily_candles").select("*", count="exact").limit(1).execute()
        count = response.count
        print(f"Daily Candles Table Count: {count}")
    except Exception as e:
        print(f"Error checking daily_candles: {e}")

if __name__ == "__main__":
    verify_data()
