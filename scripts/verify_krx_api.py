
import os
import sys
from datetime import datetime
import time

# Add backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app.services.krx_collector import krx_collector
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def verify_krx():
    dates_to_check = ["20260108", "20260109", "20260112", "20260113", "20260114"]
    
    print("--- Verifying KRX API ---")
    print(f"API Key present: {bool(os.getenv('KRX_API_KEY'))}")
    print(f"Base URL: {krx_collector.base_url}")
    
    for date_str in dates_to_check:
        print(f"\nChecking {date_str}...")
        try:
            items = krx_collector.fetch_market_ohlcv_by_date(date_str)
            print(f"  Count: {len(items)}")
            if len(items) > 0:
                print(f"  Sample: {items[0]['ticker']} {items[0]['close']}")
        except Exception as e:
            print(f"  Error: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    verify_krx()
