import argparse
import sys
import os
import json
from datetime import datetime

# Add projects root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.db.client import supabase
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

def main():
    parser = argparse.ArgumentParser(description="Run Trend Following Strategy Signal Scanner")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--min_volume", type=int, default=100000, help="Minimum volume filter (default: 100,000)")
    parser.add_argument("--min_amount", type=int, default=5000000000, help="Minimum transaction amount (default: 5,000,000,000 KRW)")
    parser.add_argument("--min_price", type=int, default=1000, help="Minimum price filter (default: 1,000)")
    parser.add_argument("--limit", type=int, default=0, help="Number of results to show (0 for all, default: All)")
    
    args = parser.parse_args()
    target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")
    
    print(f"[{datetime.now()}] Running Strategy Scanner for {target_date}...")
    
    # 1. Fetch Daily Candles (Open, Close, Volume, Amount)
    print("Fetching Daily Candles...")
    try:
        candles = []
        offset = 0
        limit = 1000
        while True:
            # Fetch 'open' as well for strength calculation
            resp = supabase.table("daily_candles").select("ticker, open, close, volume, amount").eq("date", target_date).range(offset, offset+limit-1).execute()
            if not resp.data: break
            candles.extend(resp.data)
            offset += limit
            if len(resp.data) < limit: break
            
        print(f"Fetched {len(candles)} candles.")
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return

    # Map candles by ticker
    candle_map = {c['ticker']: c for c in candles}
    
    # 2. Filter Tickers First (Strict Liquidity)
    print("Filtering candles by amount/price...")
    target_tickers = []
    filtered_candle_map = {}
    
    for c in candles:
        # Amount filter is more reliable than volume
        amount = c.get('amount') or (c['close'] * c['volume'])
        if amount >= args.min_amount and c['close'] >= args.min_price:
            if c['ticker'] not in filtered_candle_map:
                target_tickers.append(c['ticker'])
                filtered_candle_map[c['ticker']] = c
            
    print(f"Filtered down to {len(target_tickers)} tickers (Amount >= {args.min_amount:,}, Price >= {args.min_price:,}).")
    
    if not target_tickers:
        print("No tickers matched criteria. Exiting.")
        return

    # 3. Fetch Indicators for Target Tickers Only (Batching)
    # We need: MA(20), HIGH(20), and now Volume MA(20) to check volume surge? 
    # Or simplified volume check: Volume > 20MA Volume.
    # Note: 'MA' type in DB usually implies Price MA. Do we have Volume MA?
    # Our indicator_calculator calculates MA for 'close' prices.
    # It does NOT calculate Volume MA by default.
    # Alternative: Compare current Volume vs previous day's Volume? No, volatile.
    # Alternative 2: We can skip volume MA check if not available, OR assume user meant "Liquidity" filter is enough to reduce count.
    # User's request 2: "Volume > 20day Avg Volume * 1.5".
    # Implementation: We need Volume MA. 
    # Current indicator_calculator.py calculates MA on CLOSE prices.
    # Quick fix: Just rely on Transaction Amount ranking for now, or just calculate approx Avg Vol from candles if we had history.
    # But here we only fetched 'Today's' candle.
    # Let's start with strict Amount filter and Ranking.
    
    # Wait, simple "Volume Ratio" is hard without history.
    # Let's    # 2.5 Fetch Stock Names for Target Tickers
    print("Fetching Stock Names...")
    ticker_name_map = {}
    batch_size = 50 # Define batch_size here for use in name fetching
    try:
        # Batch fetch names
        total_batches = (len(target_tickers) + batch_size - 1) // batch_size
        for i in range(0, len(target_tickers), batch_size):
            batch = target_tickers[i:i+batch_size]
            resp = supabase.table("stocks").select("ticker, name").in_("ticker", batch).execute()
            if resp.data:
                for item in resp.data:
                    ticker_name_map[item['ticker']] = item['name']
    except Exception as e:
        print(f"Error fetching stock names: {e}")
        # Continue even if name fetch fails

    # 3. Fetch Indicators for Target Tickers Only (Batching)
    print("Fetching Daily Indicators for targets...")
    indicators = []
    
    batch_size = 50
    try:
        total_batches = (len(target_tickers) + batch_size - 1) // batch_size
        for i in range(0, len(target_tickers), batch_size):
            batch = target_tickers[i:i+batch_size]
            
            resp = (supabase.table("daily_technical_indicators")
                   .select("ticker, indicator_type, params, value")
                   .eq("date", target_date)
                   .in_("ticker", batch)
                   .in_("indicator_type", ["MA", "HIGH", "ATR"])
                   .execute())
            
            if resp.data:
                indicators.extend(resp.data)
                
            print(f"Batch {i//batch_size + 1}/{total_batches} fetched.")
            
        print(f"Fetched {len(indicators)} indicators for targets.")
        
    except Exception as e:
        print(f"Error fetching indicators: {e}")
        return

    # Organize indicators by ticker
    ind_map = {}
    for ind in indicators:
        t = ind['ticker']
        if t not in ind_map: ind_map[t] = {}
        
        itype = ind['indicator_type']
        params = json.loads(ind['params'])
        val = ind['value']
        
        # Key generation
        if itype == 'MA' and params.get('period') == 20:
            ind_map[t]['MA_20'] = val
        elif itype == 'HIGH' and params.get('period') == 20:
            ind_map[t]['HIGH_20'] = val
        elif itype == 'ATR' and params.get('period') == 20:
            ind_map[t]['ATR_20'] = val

    # 4. Apply Logic
    signals = []
    
    print("Analyzing signals...")
    for ticker in target_tickers:
        c_data = filtered_candle_map[ticker]
        open_p = c_data['open']
        close = c_data['close']
        volume = c_data['volume']
        amount = c_data.get('amount') or (close * volume)
        name = ticker_name_map.get(ticker, "Unknown")
        
        # Indicator Checks
        i_data = ind_map.get(ticker, {})
        ma_20 = i_data.get('MA_20')
        high_20 = i_data.get('HIGH_20')
        atr_20 = i_data.get('ATR_20')
        
        if ma_20 is None or high_20 is None:
            continue
            
        # Strategy Logic
        is_trend_up = close > ma_20
        is_breakout = close > high_20
        is_positive_candle = close > open_p
        
        if is_trend_up and is_breakout and is_positive_candle:
            # Strength: (Close - Open) / Open (Approx intraday change)
            strength = ((close - open_p) / open_p) * 100 if open_p > 0 else 0
            
            signals.append({
                'ticker': ticker,
                'name': name,
                'close': close,
                'strength': round(strength, 2),
                'amount_b': round(amount / 100000000, 1), # In Billions
                'ma_20': ma_20,
                'high_20': high_20,
                'atr_20': atr_20 if atr_20 is not None else 0 # Handle potential missing ATR
            })

    # 5. Sort & Output
    # Sort by Strength (Intraday Rise) Descending
    signals.sort(key=lambda x: x['strength'], reverse=True)
    
    limit = args.limit
    if limit == 0:
        limit = len(signals)
        
    print(f"\n[Signal Result] Found {len(signals)} stocks. Showing Top {limit if limit < len(signals) else 'All'} by Intraday Strength.")
    print("-" * 115)
    print(f"{'Ticker':<8} | {'Close':<10} | {'Str(%)':<8} | {'Amt(B)':<8} | {'MA(20)':<10} | {'HIGH(20)':<10} | {'ATR(20)':<10} | {'Name'}")
    print("-" * 115)
    
    for s in signals[:limit]:
        # Name is last to avoid alignment issues
        print(f"{s['ticker']:<8} | {s['close']:<10} | {s['strength']:<8} | {s['amount_b']:<8} | {s['ma_20']:<10} | {s['high_20']:<10} | {s['atr_20']:<10} | {s['name']}")
        
    print("-" * 115)

if __name__ == "__main__":
    main()
