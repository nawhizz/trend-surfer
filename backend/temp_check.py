"""EMA 정배열 종목 수 분석"""
import sys
sys.path.insert(0, ".")

from app.db.client import supabase

dates = ["2025-03-03", "2025-06-02", "2025-09-01", "2025-12-01"]

for date in dates:
    ema20 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "EMA").eq("params", '{"period": 20}').execute()
    ema50 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "EMA").eq("params", '{"period": 50}').execute()
    ema200 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "EMA").eq("params", '{"period": 200}').execute()
    
    d20 = {r["ticker"]: r["value"] for r in ema20.data}
    d50 = {r["ticker"]: r["value"] for r in ema50.data}
    d200 = {r["ticker"]: r["value"] for r in ema200.data}
    
    aligned = 0
    for ticker in d20:
        if ticker in d50 and ticker in d200:
            if d20[ticker] > d50[ticker] > d200[ticker]:
                aligned += 1
    
    print(f"{date}: EMA 정배열 {aligned}개 / 전체 {len(d20)}개")
