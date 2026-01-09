from pykrx import stock
from datetime import datetime, timedelta

def test_pykrx():
    today = datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
    print(f"Testing for Today: {today}")
    try:
        tickers = stock.get_market_ticker_list(today, market="KOSPI")
        print(f"KOSPI Tickers (Today): {len(tickers)}")
    except Exception as e:
        print(f"Error (Today): {e}")

    print(f"Testing for Yesterday: {yesterday}")
    try:
        tickers = stock.get_market_ticker_list(yesterday, market="KOSPI")
        print(f"KOSPI Tickers (Yesterday): {len(tickers)}")
    except Exception as e:
        print(f"Error (Yesterday): {e}")

    print("Testing for Historical Date: 20240502")
    try:
        tickers = stock.get_market_ticker_list("20240502", market="KOSPI")
        print(f"KOSPI Tickers (20240502): {len(tickers)}")
    except Exception as e:
        print(f"Error (20240502): {e}")

if __name__ == "__main__":
    test_pykrx()
