import argparse
import sys
import os
from datetime import datetime

# Add projects root to path to allow importing app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.indicator_calculator import indicator_calculator
from app.core.logger import get_logger
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Run Daily Indicator Calculation")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")

    args = parser.parse_args()

    target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")

    logger.info(f"일일 지표 계산 시작: {target_date}")

    indicator_calculator.calculate_and_save_for_all_tickers(
        start_date=target_date,
        end_date=target_date
    )

    logger.info("일일 지표 계산 완료")

if __name__ == "__main__":
    main()
