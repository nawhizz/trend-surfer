"""
백테스트 거래 결과 상세 분석
"""
from app.db.client import supabase

# None 값 처리 함수
def safe_float(val):
    try:
        if val is None:
            return 0.0
        return float(val)
    except:
        return 0.0

print("=== 최근 백테스트 거래 분석 ===\n")

# 최근 세션의 거래 기록 조회
resp = (
    supabase.table("backtest_trades")
    .select("*")
    .order("session_id", desc=True)
    .limit(50)
    .execute()
)

if not resp.data:
    print("거래 기록 없음")
    exit()

trades = resp.data

# 세션별 그룹화
sessions = {}
for t in trades:
    sid = t["session_id"]
    if sid not in sessions:
        sessions[sid] = []
    sessions[sid].append(t)

# 최근 세션 분석
latest_session = list(sessions.keys())[0]
latest_trades = sessions[latest_session]

print(f"세션 ID: {latest_session}")
print(f"총 거래 수: {len(latest_trades)}")

# 결과를 파일로 저장
with open("trade_analysis_result.txt", "w", encoding="utf-8") as f:
    f.write("=== 최근 백테스트 거래 분석 ===\n\n")
    f.write(f"세션 ID: {latest_session}\n")
    f.write(f"총 거래 수: {len(latest_trades)}\n")

    # 승패 분석
    wins = [t for t in latest_trades if safe_float(t.get("pnl")) > 0]
    losses = [t for t in latest_trades if safe_float(t.get("pnl")) <= 0]

    f.write(f"승리: {len(wins)}건, 패배: {len(losses)}건\n")
    
    if latest_trades:
        win_rate = len(wins)/len(latest_trades)*100
        f.write(f"승률: {win_rate:.1f}%\n")

    # 손익비
    if wins:
        avg_win = sum(safe_float(t.get("pnl")) for t in wins) / len(wins)
        f.write(f"평균 수익: {avg_win:+,.0f}원\n")
    else:
        avg_win = 0
        
    if losses:
        avg_loss = sum(safe_float(t.get("pnl")) for t in losses) / len(losses)
        f.write(f"평균 손실: {avg_loss:+,.0f}원\n")
    else:
        avg_loss = 0

    if avg_loss != 0:
        f.write(f"손익비: {abs(avg_win/avg_loss):.2f}\n")

    # 청산 사유별 분석
    f.write("\n### 청산 사유별 분석 ###\n")
    by_reason = {}
    for t in latest_trades:
        reason = t.get("exit_reason", "UNKNOWN")
        if reason not in by_reason:
            by_reason[reason] = {"count": 0, "pnl": 0, "r_sum": 0}
        by_reason[reason]["count"] += 1
        by_reason[reason]["pnl"] += safe_float(t.get("pnl"))
        by_reason[reason]["r_sum"] += safe_float(t.get("r_multiple"))

    for reason, stats in by_reason.items():
        avg_r = stats["r_sum"] / stats["count"] if stats["count"] > 0 else 0
        f.write(f"{reason}: {stats['count']}건, 총손익: {stats['pnl']:+,.0f}원, 평균R: {avg_r:+.2f}\n")

    # 개별 거래 상세
    f.write("\n### 개별 거래 상세 ###\n")
    for t in latest_trades:
        ticker = t.get("ticker", "N/A")
        entry_date = t.get("entry_date", "N/A")
        exit_date = t.get("exit_date", "N/A")
        pnl = safe_float(t.get("pnl"))
        r_mult = safe_float(t.get("r_multiple"))
        reason = t.get("exit_reason", "N/A")
        
        # 보유 기간 계산
        try:
            from datetime import datetime
            entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
            exit_dt = datetime.strptime(exit_date, "%Y-%m-%d")
            hold_days = (exit_dt - entry_dt).days
        except:
            hold_days = "?"
        
        f.write(f"{ticker} | {entry_date} -> {exit_date} ({hold_days}일) | "
              f"R: {r_mult:+.2f} | PnL: {pnl:+,.0f} | {reason}\n")

print("분석 결과가 trade_analysis_result.txt에 저장되었습니다.")
