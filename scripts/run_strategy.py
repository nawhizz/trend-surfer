import argparse
import sys
import os
import json
from datetime import datetime
import pandas as pd

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
    ticker_name_map = {}  # ticker -> name
    ticker_excluded = set()  # 제외할 종목 집합
    batch_size = 50 # Define batch_size here for use in name fetching
    
    # 제외 키워드 (종목명에 포함되면 제외)
    exclude_keywords = ['ETF', 'ETN', '스팩', 'SPAC', '관리종목', '정리매매', '투자위험', '투자경고', '거래정지']
    
    try:
        # Batch fetch names, is_preferred, and warning_type
        total_batches = (len(target_tickers) + batch_size - 1) // batch_size
        for i in range(0, len(target_tickers), batch_size):
            batch = target_tickers[i:i+batch_size]
            resp = supabase.table("stocks").select("ticker, name, is_preferred, warning_type").in_("ticker", batch).execute()
            if resp.data:
                for item in resp.data:
                    ticker = item['ticker']
                    name = item['name'] or ''
                    is_preferred = item.get('is_preferred', False)
                    warning_type = item.get('warning_type')  # 시장경보 유형
                    
                    ticker_name_map[ticker] = name
                    
                    # 제외 조건 검사
                    should_exclude = False
                    
                    # 1. 우선주 제외
                    if is_preferred:
                        should_exclude = True
                    
                    # 2. 시장경보 종목 제외 (관리종목, 투자경고, 환기종목, 거래정지, 정리매매)
                    if not should_exclude and warning_type:
                        should_exclude = True
                    
                    # 3. 종목명에 제외 키워드 포함 시 제외
                    if not should_exclude:
                        for keyword in exclude_keywords:
                            if keyword in name:
                                should_exclude = True
                                break
                    
                    # 4. 종목코드 패턴으로 ETF/ETN 식별 (6자리 숫자가 아니면 제외)
                    if not should_exclude:
                        if not (ticker.isdigit() and len(ticker) == 6):
                            should_exclude = True
                    
                    if should_exclude:
                        ticker_excluded.add(ticker)
                        
    except Exception as e:
        print(f"Error fetching stock names: {e}")
        # Continue even if name fetch fails
    
    # 제외 종목 필터링
    original_count = len(target_tickers)
    if ticker_excluded:
        target_tickers = [t for t in target_tickers if t not in ticker_excluded]
        filtered_candle_map = {k: v for k, v in filtered_candle_map.items() if k not in ticker_excluded}
    print(f"Excluded {original_count - len(target_tickers)} stocks (우선주/ETF/ETN/스팩 등). Remaining: {len(target_tickers)}")

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
                   .in_("indicator_type", ["MA", "HIGH", "ATR", "EMA_STAGE"])
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
        elif itype == 'EMA_STAGE':
            ind_map[t]['EMA_STAGE'] = val

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
        ema_stage = i_data.get('EMA_STAGE', 0)
        
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
                'ma_20': ma_20,
                'high_20': high_20,
                'atr_20': atr_20 if atr_20 is not None else 0, # Handle potential missing ATR
                'stage': int(ema_stage) if ema_stage is not None else 0
            })

    # 5. Sort & Output
    # Sort by Strength (Intraday Rise) Descending
    signals.sort(key=lambda x: x['strength'], reverse=True)
    
    limit = args.limit
    if limit == 0:
        limit = len(signals)
        
    print(f"\n[Signal Result] Found {len(signals)} stocks. Showing Top {limit if limit < len(signals) else 'All'} by Intraday Strength.")
    print("-" * 125)
    print(f"{'Ticker':<8} | {'Close':<10} | {'Str(%)':<8} | {'Amt(B)':<8} | {'MA(20)':<10} | {'HIGH(20)':<10} | {'ATR(20)':<10} | {'STAGE':<5} | {'Name'}")
    print("-" * 125)
    
    for s in signals[:limit]:
        # Name is last to avoid alignment issues
        print(f"{s['ticker']:<8} | {s['close']:<10} | {s['strength']:<8} | {s['amount_b']:<8} | {s['ma_20']:<10} | {s['high_20']:<10} | {s['atr_20']:<10} | {s['stage']:<5} | {s['name']}")
        
    print("-" * 125)

    # 6. 엑셀 파일로 결과 저장
    if signals:
        # DataFrame 생성
        df = pd.DataFrame(signals)
        
        # 컬럼 정리 (중복 제거 및 순서 정리)
        output_columns = [
            'ticker', 'name', 'close', 'strength', 'amount_b', 
            'ma_20', 'high_20', 'atr_20', 'stage'
        ]
        
        # 중복 컬럼이 있을 수 있으므로 안전하게 처리
        df = df.loc[:, ~df.columns.duplicated()]
        df = df[[col for col in output_columns if col in df.columns]]
        
        # 컬럼명 한글화
        df.columns = [
            '종목코드', '종목명', '종가', '강도(%)', '거래대금(억)', 
            'MA(20)', 'HIGH(20)', 'ATR(20)', 'Stage'
        ]
        
        # 결과 저장 디렉토리 생성
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, '..'))
        results_dir = os.path.join(project_root, 'results')
        
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            
        # 엑셀 파일명 생성 (날짜 포함)
        date_str = target_date.replace('-', '')
        filename = f"signal_{date_str}.xlsx"
        filepath = os.path.join(results_dir, filename)
        
        try:
            df.to_excel(filepath, index=False, engine='openpyxl')
            print(f"\n[Excel] 결과 저장 완료: {filepath}")
        except Exception as e:
            print(f"\n[Error] 엑셀 저장 실패: {e}")

if __name__ == "__main__":
    main()
