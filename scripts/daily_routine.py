import subprocess
import sys
import os
import argparse
from datetime import datetime

# Script Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable

def run_script(script_name, args=[]):
    script_path = os.path.join(BASE_DIR, script_name)
    cmd = [PYTHON_EXE, script_path] + args
    
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] Step Started: {script_name} {' '.join(args)}")
    print(f"{'='*60}")
    
    try:
        # Stream output to console
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True, 
            encoding='utf-8',
            errors='replace' # Handle potential encoding issues
        )
        
        for line in process.stdout:
            # print() relies on PYTHONIOENCODING=utf-8 set in batch file
            print(line, end='')
            
        process.wait()
        
        if process.returncode != 0:
            print(f"\n[ERROR] {script_name} failed with exit code {process.returncode}")
            return False
            
        print(f"[{datetime.now()}] Step Completed: {script_name}")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Failed to execute {script_name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Trend Surfer Daily Routine")
    parser.add_argument("--date", help="Target Date YYYY-MM-DD (default: today)")
    parser.add_argument("--skip_tickers", action="store_true", help="Skip ticker update step")
    parser.add_argument("--skip_adjust", action="store_true", help="Skip adjustment check step")
    
    args = parser.parse_args()
    
    target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now()}] Starting Daily Routine for {target_date}")
    
    # 1. Update Tickers based on Master
    if not args.skip_tickers:
        if not run_script("run_collector.py", ["--mode", "tickers"]):
            print("Routine aborted at Step 1.")
            sys.exit(1)
    
    # 2. Check Adjusted Prices & Backfill/Recalculate
    if not args.skip_adjust:
        # Default backfill start 2020-01-01 as per plan
        if not run_script("update_adjusted_prices.py", ["--date", target_date, "--start_date", "2020-01-01"]):
             print("Routine aborted at Step 2.")
             sys.exit(1)
             
    # 3. Collect Today's Prices
    # Note: run_collector.py --mode daily fetches data from KRX/FDR for 'Today' (or target date)
    if not run_script("run_collector.py", ["--mode", "daily", "--date", target_date]):
        print("Routine aborted at Step 3.")
        sys.exit(1)
        
    # 4. Calculate Daily Indicators
    if not run_script("run_daily_indicators.py", ["--date", target_date]):
        print("Routine aborted at Step 4.")
        sys.exit(1)
        
    # 5. Update Warning Stocks (관리종목, 투자경고 등)
    if not run_script("update_warning_stocks.py"):
        print("Warning: Step 5 (Warning Stocks) failed, continuing...")
        # 경고 종목 업데이트 실패해도 계속 진행

    # 6. Run Strategy & Generate Signals
    if not run_script("run_strategy.py", ["--date", target_date]):
        print("Routine aborted at Step 6.")
        sys.exit(1)
        
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] Daily Routine Finished Successfully.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
