from pykrx import stock
import inspect

print("--- stock.get_market_ohlcv ---")
try:
    print(inspect.signature(stock.get_market_ohlcv))
except Exception as e:
    print(e)

print("\n--- stock.get_market_ohlcv_by_date ---")
try:
    print(inspect.signature(stock.get_market_ohlcv_by_date))
except Exception as e:
    print(e)

# Check for any method that might look like 'by_ticker'
print("\n--- Listing stock module attributes ---")
dl = dir(stock)
print([d for d in dl if 'ohlcv' in d])
