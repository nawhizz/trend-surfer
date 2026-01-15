import argparse
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.hybrid_collector import hybrid_collector
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def main():
    parser = argparse.ArgumentParser(description='Backfill historical daily candles (Hybrid: FDR Adjusted + KRX Amount).')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    
    args = parser.parse_args()

    # Validate Dates
    try:
        datetime.strptime(args.start, "%Y-%m-%d")
        datetime.strptime(args.end, "%Y-%m-%d")
    except ValueError:
        print("Error: Dates must be in YYYY-MM-DD format.")
        sys.exit(1)

    print(f"Starting Hybrid Backfill from {args.start} to {args.end}...")
    
    hybrid_collector.backfill_hybrid(args.start, args.end)
    print("Backfill process completed.")

if __name__ == "__main__":
    main()

