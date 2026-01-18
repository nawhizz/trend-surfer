"""
백테스트 거래 결과 상세 분석 (거래 매칭 기능 포함)
"""
from app.db.client import supabase
from datetime import datetime

# None 값 처리 함수
def safe_float(val):
    try:
        if val is None:
            return 0.0
        return float(val)
    except:
        return 0.0

print("=== 최근 백테스트 거래 분석 (매칭) ===\n")

# 최근 세션 조회
sess_resp = (
    supabase.table("backtest_sessions")
    .select("id")
    .order("created_at", desc=True)
    .limit(1)
    .execute()
)
if not sess_resp.data:
    print("세션 없음")
    exit()

session_id = sess_resp.data[0]["id"]
print(f"세션 ID: {session_id}")

# 해당 세션의 모든 거래 기록 조회
resp = (
    supabase.table("backtest_trades")
    .select("*")
    .eq("session_id", session_id)
    .order("trade_date")
    .execute()
)

if not resp.data:
    print("거래 기록 없음")
    exit()

raw_trades = resp.data
print(f"총 트랜잭션 수: {len(raw_trades)}")

# 거래 매칭 (FIFO)
positions = {} # ticker -> list of buy trades
closed_trades = []
open_positions = []

for t in raw_trades:
    ticker = t["ticker"]
    trade_type = t["trade_type"]
    
    if trade_type == "BUY":
        if ticker not in positions:
            positions[ticker] = []
        positions[ticker].append(t)
        
    elif trade_type == "SELL":
        if ticker in positions and positions[ticker]:
            # FIFO: 가장 먼저 들어온 매수분과 매칭
            buy_trade = positions[ticker].pop(0)
            
            closed_trade = {
                "ticker": ticker,
                "entry_date": buy_trade["trade_date"],
                "entry_price": buy_trade["price"],
                "exit_date": t["trade_date"],
                "exit_price": t["price"],
                "exit_reason": t["exit_reason"],
                "pnl": t["pnl"],
                "r_multiple": t["r_multiple"],
                "hold_days": 0
            }
            
            # 보유 기간
            try:
                entry_dt = datetime.strptime(buy_trade["trade_date"], "%Y-%m-%d")
                exit_dt = datetime.strptime(t["trade_date"], "%Y-%m-%d")
                closed_trade["hold_days"] = (exit_dt - entry_dt).days
            except:
                pass
                
            closed_trades.append(closed_trade)
        else:
            print(f"⚠️ 매수 없는 매도 발생: {ticker} on {t['trade_date']}")

# 남은 포지션 (오픈 상태)
for ticker, buys in positions.items():
    for b in buys:
        open_positions.append(b)

# 결과 출력 및 저장
with open("trade_analysis_result_matched.txt", "w", encoding="utf-8") as f:
    f.write(f"=== 세션 {session_id} 분석 ===\n")
    f.write(f"청산 완료 거래: {len(closed_trades)}건\n")
    f.write(f"미청산 포지션: {len(open_positions)}건\n\n")
    
    # 승패 분석
    wins = [t for t in closed_trades if safe_float(t.get("pnl")) > 0]
    losses = [t for t in closed_trades if safe_float(t.get("pnl")) <= 0]
    
    f.write(f"승리: {len(wins)}건, 패배: {len(losses)}건\n")
    if closed_trades:
        win_rate = len(wins) / len(closed_trades) * 100
        f.write(f"승률: {win_rate:.1f}%\n")
        
        total_pnl = sum(safe_float(t.get("pnl")) for t in closed_trades)
        f.write(f"총 실현 손익: {total_pnl:+,.0f}원\n")
        
        # 손익비
        avg_win = sum(safe_float(t.get("pnl")) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(safe_float(t.get("pnl")) for t in losses) / len(losses) if losses else 0
        
        f.write(f"평균 수익: {avg_win:+,.0f}원\n")
        f.write(f"평균 손실: {avg_loss:+,.0f}원\n")
        
        if avg_loss != 0:
            f.write(f"손익비: {abs(avg_win/avg_loss):.2f}\n")
            
    # 청산 사유별
    f.write("\n### 청산 사유별 통계 ###\n")
    by_reason = {}
    for t in closed_trades:
        reason = t.get("exit_reason", "UNKNOWN")
        if reason not in by_reason:
            by_reason[reason] = {"count": 0, "pnl": 0, "r_sum": 0}
        
        by_reason[reason]["count"] += 1
        by_reason[reason]["pnl"] += safe_float(t.get("pnl"))
        by_reason[reason]["r_sum"] += safe_float(t.get("r_multiple"))
        
    for reason, stats in by_reason.items():
        avg_r = stats["r_sum"] / stats["count"] if stats["count"] > 0 else 0
        f.write(f"{reason}: {stats['count']}건, 총손익: {stats['pnl']:+,.0f}원, 평균R: {avg_r:+.2f}\n")
        
    # 거래 상세
    f.write("\n### 청산 거래 상세 목록 ###\n")
    for t in closed_trades:
        f.write(f"{t['ticker']} | {t['entry_date']} -> {t['exit_date']} ({t['hold_days']}일) | "
                f"R: {safe_float(t['r_multiple']):+.2f} | PnL: {safe_float(t['pnl']):+,.0f} | {t['exit_reason']}\n")

    # 미청산 상세
    f.write("\n### 미청산 포지션 목록 ###\n")
    for t in open_positions:
        f.write(f"{t['ticker']} | 진입: {t['trade_date']} | 가격: {t['price']}\n")

print("분석 완료: trade_analysis_result_matched.txt")
