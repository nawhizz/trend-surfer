from supabase import create_client
import os
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY")

supabase = create_client(url, key)

def verify_preferred():
    print("Verifying Preferred Stocks...")
    
    # Check Samsung Electronics Pref (005935)
    try:
        response = supabase.table("stocks").select("ticker, name, is_preferred").eq("ticker", "005935").execute()
        if response.data:
            print(f"Samsung Elec Pref (005935): {response.data[0]}")
        else:
            print("Samsung Elec Pref (005935) not found.")
            
        # Check Samsung Electronics Common (005930)
        response = supabase.table("stocks").select("ticker, name, is_preferred").eq("ticker", "005930").execute()
        if response.data:
            print(f"Samsung Elec Common (005930): {response.data[0]}")
            
        # Count total preferred
        response = supabase.table("stocks").select("*", count="exact").eq("is_preferred", True).limit(1).execute()
        print(f"Total Preferred Stocks: {response.count}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_preferred()
