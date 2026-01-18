"""RSI 및 기타 지표 재계산 (200개 종목)"""
import sys
sys.path.insert(0, ".")

from app.db.client import supabase
from app.services.indicator_calculator import indicator_calculator

# 1. 200개 종목 조회
response = (
    supabase.table("stocks")
    .select("ticker")
    .eq("is_active", True)
    .eq("is_preferred", False)
    .neq("market", "INDEX")
    .range(0, 199)
    .execute()
)
tickers = [row["ticker"] for row in response.data]
print(f"Target tickers: {len(tickers)}")

# 2. 재계산 실행 (2025-01-01부터)
indicator_calculator.calculate_and_save_for_all_tickers(
    start_date="2025-01-01",
    ticker_list=tickers
)
print("Done.")
