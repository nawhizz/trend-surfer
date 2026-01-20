import argparse
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))
from app.services.collector import collector
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def main():
    parser = argparse.ArgumentParser(description="Run Stock Collector")
    parser.add_argument("--mode", required=True, choices=['tickers', 'daily'], help="Collection mode: 'tickers' (Update Master) or 'daily' (Fetch Today's Price)")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today, only used for 'daily' mode)")
    
    args = parser.parse_args()
    
    if args.mode == 'tickers':
        print("Running Stock List Update...")
        collector.update_stock_list()
    elif args.mode == 'daily':
        target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")
        print(f"Running Daily Candle Collection for {target_date}...")
        collector.fetch_daily_ohlcv(target_date)

    print("Done.")

if __name__ == "__main__":
    main()
