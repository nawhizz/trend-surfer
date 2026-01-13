from pykrx import stock
import inspect

methods = [
    'get_market_ohlcv',
    'get_market_ohlcv_by_date',
    'get_market_ohlcv_by_ticker', # Check if this exists
    'get_market_price_change_by_ticker'
]

print("--- Checking PyKRX Methods ---")
for m in methods:
    if hasattr(stock, m):
        func = getattr(stock, m)
        try:
            sig = inspect.signature(func)
            print(f"FAILED?? No, found: {m}{sig}")
        except:
             print(f"Found {m} but could not get signature")
    else:
        print(f"Method {m} NOT found")
