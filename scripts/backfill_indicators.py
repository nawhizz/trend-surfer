import argparse
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.indicator_calculator import indicator_calculator
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def main():
    parser = argparse.ArgumentParser(description='Backfill technical indicators (SMA, EMA, etc.) based on daily candles.')
    parser.add_argument('--start', required=False, help='Start date (YYYY-MM-DD). If omitted, calculates for all available history.')
    parser.add_argument('--end', required=False, help='End date (YYYY-MM-DD). If omitted, calculates up to the latest date.')
    parser.add_argument('--ticker', required=False, help='Specific ticker code to process. If omitted, processes all active tickers.')
    
    args = parser.parse_args()

    # Validate Dates if provided
    if args.start:
        try:
            datetime.strptime(args.start, "%Y-%m-%d")
        except ValueError:
            print("Error: Start date must be in YYYY-MM-DD format.")
            sys.exit(1)
            
    if args.end:
        try:
            datetime.strptime(args.end, "%Y-%m-%d")
        except ValueError:
            print("Error: End date must be in YYYY-MM-DD format.")
            sys.exit(1)

    print(f"Starting Indicator Backfill...")
    if args.start:
        print(f"  Start Date: {args.start}")
    if args.end:
        print(f"  End Date: {args.end}")
    if args.ticker:
        print(f"  Target Ticker: {args.ticker}")
    else:
        print(f"  Target Ticker: ALL")
    
    ticker_list = [args.ticker] if args.ticker else None
    
    try:
        indicator_calculator.calculate_and_save_for_all_tickers(
            start_date=args.start,
            end_date=args.end,
            ticker_list=ticker_list
        )
        print("\nBackfill process completed successfully.")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
