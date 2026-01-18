
import sys
import os
from pprint import pprint
import pandas as pd
from datetime import datetime

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.client import supabase

def debug_logic_analysis():
    # 알테오젠(196170) 분석
    ticker = "196170" 
    start_date = "2024-01-01"
    end_date = "2024-06-30"

    print(f"Checking data for {ticker} from {start_date} to {end_date}...")

    # 1. Fetch Candles
    candles = supabase.table("daily_candles").select("date, close").eq("ticker", ticker).gte("date", start_date).lte("date", end_date).order("date").limit(1000).execute().data
    
    if not candles:
        print("No candle data found!")
        return

    df_price = pd.DataFrame(candles)
    df_price['date'] = pd.to_datetime(df_price['date']).dt.strftime('%Y-%m-%d')
    df_price.set_index('date', inplace=True)

    # 2. Fetch Indicators
    indicators = supabase.table("daily_technical_indicators").select("date, indicator_type, value, params").eq("ticker", ticker).gte("date", start_date).lte("date", end_date).limit(10000).execute().data
    
    data_map = {} 

    for row in indicators:
        d = row['date']
        itype = row['indicator_type']
        val = row['value']
        params = row['params']

        if d not in data_map:
            data_map[d] = {}
        
        # params load
        if isinstance(params, str):
            try:
                import json
                params = json.loads(params)
            except:
                try: 
                    import ast
                    params = ast.literal_eval(params)
                except:
                    pass
        
        p = params.get('period')
        
        if itype == 'HIGH' and str(p) == '20':
            data_map[d]['high20'] = val
        elif itype == 'EMA_SLOPE' and str(p) == '50':
            data_map[d]['slope'] = val
        elif itype == 'ATR' and str(p) == '20':
            data_map[d]['atr'] = val

    # 3. Analyze Entry Logic
    print(f"{'Date':<12} {'Close':<10} {'High20':<10} {'Slope':<8} {'ATR%':<8} {'Break?':<6} {'Slope?':<6} {'ATR?':<6}")
    print("-" * 80)
    
    for d, row in df_price.iterrows():
        close = row['close']
        inds = data_map.get(d, {})
        
        high20 = inds.get('high20')
        slope = inds.get('slope')
        atr = inds.get('atr')

        if high20 is None or slope is None or atr is None:
            continue
            
        atr_ratio = (atr / close)
        
        is_breakout = close > high20
        is_slope_ok = slope >= -0.2
        is_atr_ok = atr_ratio <= 0.15 # Tuned value logic analysis
        
        if is_breakout:
            print(f"{d:<12} {close:<10} {high20:<10.0f} {slope:<8.2f} {atr_ratio:<8.2%} {str(is_breakout):<6} {str(is_slope_ok):<6} {str(is_atr_ok):<6}")

if __name__ == "__main__":
    debug_logic_analysis()
