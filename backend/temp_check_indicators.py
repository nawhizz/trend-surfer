"""지표 데이터 확인"""
import sys
sys.path.insert(0, ".")

from app.db.client import supabase
import json

ticker = "005930"  # 삼성전자
date = "2025-06-02"

# MA_200 확인
ma200 = supabase.table("daily_technical_indicators")\
    .select("*")\
    .eq("ticker", ticker)\
    .eq("date", date)\
    .eq("indicator_type", "MA")\
    .like("params", "%200%")\
    .execute()

print("MA_200:", ma200.data)

# RSI_14 확인
rsi14 = supabase.table("daily_technical_indicators")\
    .select("*")\
    .eq("ticker", ticker)\
    .eq("indicator_type", "RSI")\
    .execute()

print("RSI 데이터 샘플:", rsi14.data[:2])
