
import sys
import os

# Add backend to path (self)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.client import supabase

def add_alteozen():
    ticker = "196170"
    name = "알테오젠"
    market = "KOSDAQ"
    
    data = {
        "ticker": ticker,
        "name": name,
        "market": market,
        "is_active": True
    }
    
    print(f"Adding {name} ({ticker})...")
    try:
        supabase.table("stocks").upsert(data).execute()
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_alteozen()
