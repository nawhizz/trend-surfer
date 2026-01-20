import argparse
import sys
import os
from datetime import datetime

# Add projects root to path to allow importing app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.indicator_calculator import indicator_calculator
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def main():
    parser = argparse.ArgumentParser(description="Run Daily Indicator Calculation")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    
    args = parser.parse_args()
    
    target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")
    
    print(f"[{datetime.now()}] Starting Daily Indicator Calculation for {target_date}...")
    
    # We set start_date and end_date to target_date to only SAVE records for that day.
    # The calculator internally fetches historical candles needed for calculation.
    indicator_calculator.calculate_and_save_for_all_tickers(
        start_date=target_date,
        end_date=target_date
    )
    
    print("Daily Indicator Calculation Completed.")

if __name__ == "__main__":
    main()
