"""EMA 정배열 분석"""
import sys
sys.path.insert(0, ".")

from app.db.client import supabase
import json

date = "2025-06-02"

# EMA_20 조회
params_20 = json.dumps({"period": 20})
params_50 = json.dumps({"period": 50})
params_200 = json.dumps({"period": 200})

ema20 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "EMA").eq("params", params_20).limit(500).execute()
ema50 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "EMA").eq("params", params_50).limit(500).execute()
ema200 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "EMA").eq("params", params_200).limit(500).execute()

print(f"EMA_20 데이터: {len(ema20.data)}개")
print(f"EMA_50 데이터: {len(ema50.data)}개")
print(f"EMA_200 데이터: {len(ema200.data)}개")

d20 = {r["ticker"]: r["value"] for r in ema20.data}
d50 = {r["ticker"]: r["value"] for r in ema50.data}
d200 = {r["ticker"]: r["value"] for r in ema200.data}

aligned = 0
for ticker in d20:
    if ticker in d50 and ticker in d200:
        if d20[ticker] > d50[ticker] > d200[ticker]:
            aligned += 1

print(f"\nEMA 정배열 (20>50>200): {aligned}개")

# SMA도 비교
params_ma20 = json.dumps({"period": 20})
params_ma60 = json.dumps({"period": 60})
params_ma120 = json.dumps({"period": 120})

ma20 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "MA").eq("params", params_ma20).limit(500).execute()
ma60 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "MA").eq("params", params_ma60).limit(500).execute()
ma120 = supabase.table("daily_technical_indicators").select("ticker, value").eq("date", date).eq("indicator_type", "MA").eq("params", params_ma120).limit(500).execute()

dm20 = {r["ticker"]: r["value"] for r in ma20.data}
dm60 = {r["ticker"]: r["value"] for r in ma60.data}
dm120 = {r["ticker"]: r["value"] for r in ma120.data}

sma_aligned = 0
for ticker in dm20:
    if ticker in dm60 and ticker in dm120:
        if dm20[ticker] > dm60[ticker] > dm120[ticker]:
            sma_aligned += 1

print(f"SMA 정배열 (20>60>120): {sma_aligned}개")
