"""
BacktestResult - 백테스트 결과 분석 및 리포트

상세 통계 계산, CSV 출력, 시각화 기능을 제공합니다.
"""

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.backtest.portfolio import Trade, DailyRecord


@dataclass
class BacktestStats:
    """
    백테스트 상세 통계
    """
    # 기본 정보
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float

    # 수익률 지표
    total_return_pct: float         # 총 수익률 (%)
    cagr: float                     # 연평균 수익률 (%)

    # 거래 통계
    total_trades: int               # 총 거래 수
    winning_trades: int             # 승리 수
    losing_trades: int              # 손실 수
    win_rate: float                 # 승률 (%)

    # 손익 통계
    total_pnl: float                # 총 손익 (원)
    avg_win: float                  # 평균 수익 (원)
    avg_loss: float                 # 평균 손실 (원)
    profit_factor: float            # 손익비 (총수익/총손실)
    avg_r_multiple: float           # 평균 R 배수

    # 리스크 지표
    max_drawdown_pct: float         # 최대 낙폭 (%)
    max_drawdown_amount: float      # 최대 낙폭 (원)
    max_drawdown_date: str          # 최대 낙폭 발생일
    sharpe_ratio: float             # 샤프 비율 (연율화)

    # 기간 통계
    avg_holding_days: float         # 평균 보유 기간 (일)
    max_consecutive_wins: int       # 최대 연속 승
    max_consecutive_losses: int     # 최대 연속 패


class BacktestResult:
    """
    백테스트 결과 분석기
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float,
        final_equity: float,
        trades: list[Trade],
        daily_records: list[DailyRecord],
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.final_equity = final_equity
        self.trades = trades
        self.daily_records = daily_records

    def calculate_stats(self) -> BacktestStats:
        """
        상세 통계 계산
        """
        try:
            # 기본 수익률
            total_return_pct = (self.final_equity - self.initial_capital) / self.initial_capital * 100 if self.initial_capital > 0 else 0.0

            # CAGR 계산
            days = self._calculate_days()
            years = days / 365 if days > 0 else 1
            if self.final_equity > 0 and self.initial_capital > 0:
                cagr = ((self.final_equity / self.initial_capital) ** (1 / years) - 1) * 100
            else:
                cagr = 0.0

            # 거래 통계
            total_trades = len(self.trades) if self.trades else 0
            winning_trades = len([t for t in self.trades if t.pnl > 0]) if self.trades else 0
            losing_trades = len([t for t in self.trades if t.pnl <= 0]) if self.trades else 0
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

            # 손익 통계
            total_pnl = sum(t.pnl for t in self.trades) if self.trades else 0
            
            wins = [t.pnl for t in self.trades if t.pnl > 0] if self.trades else []
            losses = [abs(t.pnl) for t in self.trades if t.pnl < 0] if self.trades else []
            
            avg_win = sum(wins) / len(wins) if wins else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0
            
            total_wins = sum(wins) if wins else 0
            total_losses = sum(losses) if losses else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

            # 평균 R 배수
            r_multiples = [t.r_multiple for t in self.trades if t.r_multiple is not None] if self.trades else []
            avg_r_multiple = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0

            # 최대 낙폭 (MDD)
            mdd_pct, mdd_amount, mdd_date = self._calculate_mdd()

            # 샤프 비율
            sharpe = self._calculate_sharpe()

            # 평균 보유 기간
            avg_holding_days = self._calculate_avg_holding_days()

            # 연속 승패
            max_wins, max_losses = self._calculate_streaks()

            return BacktestStats(
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.initial_capital,
                final_equity=self.final_equity,
                total_return_pct=total_return_pct,
                cagr=cagr,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                avg_r_multiple=avg_r_multiple,
                max_drawdown_pct=mdd_pct,
                max_drawdown_amount=mdd_amount,
                max_drawdown_date=mdd_date,
                sharpe_ratio=sharpe,
                avg_holding_days=avg_holding_days,
                max_consecutive_wins=max_wins,
                max_consecutive_losses=max_losses,
            )
        except Exception as e:
            # 에러 발생 시 기본값 반환
            return BacktestStats(
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.initial_capital,
                final_equity=self.final_equity,
                total_return_pct=0.0,
                cagr=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                avg_r_multiple=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_amount=0.0,
                max_drawdown_date="",
                sharpe_ratio=0.0,
                avg_holding_days=0.0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
            )

    def _calculate_days(self) -> int:
        """백테스트 기간 (일)"""
        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
            end = datetime.strptime(self.end_date, "%Y-%m-%d")
            return (end - start).days
        except ValueError:
            return 0

    def _calculate_mdd(self) -> tuple[float, float, str]:
        """최대 낙폭 계산"""
        if not self.daily_records:
            return 0.0, 0.0, ""

        peak = self.initial_capital
        max_dd_pct = 0.0
        max_dd_amount = 0.0
        max_dd_date = ""

        for record in self.daily_records:
            if record.equity > peak:
                peak = record.equity

            dd_amount = peak - record.equity
            dd_pct = (dd_amount / peak * 100) if peak > 0 else 0.0

            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_amount = dd_amount
                max_dd_date = record.date

        return max_dd_pct, max_dd_amount, max_dd_date

    def _calculate_sharpe(self, risk_free_rate: float = 0.03) -> float:
        """샤프 비율 계산 (연율화)"""
        try:
            if len(self.daily_records) < 2:
                return 0.0

            # 일별 수익률 계산
            daily_returns = []
            for i in range(1, len(self.daily_records)):
                prev = self.daily_records[i - 1].equity
                curr = self.daily_records[i].equity
                if prev > 0:
                    daily_returns.append((curr - prev) / prev)

            if len(daily_returns) < 2:
                return 0.0

            # 평균 및 표준편차
            import statistics
            avg_return = statistics.mean(daily_returns)
            std_return = statistics.stdev(daily_returns)

            if std_return == 0 or std_return != std_return:  # NaN 체크
                return 0.0

            # 연율화 (거래일 기준 252일)
            annual_return = avg_return * 252
            annual_std = std_return * (252 ** 0.5)
            sharpe = (annual_return - risk_free_rate) / annual_std

            return sharpe
        except Exception:
            return 0.0

    def _calculate_avg_holding_days(self) -> float:
        """평균 보유 기간 계산"""
        if not self.trades:
            return 0.0

        holding_days = []
        for trade in self.trades:
            try:
                entry = datetime.strptime(trade.entry_date, "%Y-%m-%d")
                exit = datetime.strptime(trade.exit_date, "%Y-%m-%d")
                holding_days.append((exit - entry).days)
            except ValueError:
                continue

        return sum(holding_days) / len(holding_days) if holding_days else 0.0

    def _calculate_streaks(self) -> tuple[int, int]:
        """연속 승패 계산"""
        if not self.trades:
            return 0, 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in self.trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def print_summary(self):
        """통계 요약 출력"""
        stats = self.calculate_stats()

        print("\n" + "=" * 60)
        print("📊 백테스트 상세 결과")
        print("=" * 60)

        print(f"\n📅 기간: {stats.start_date} ~ {stats.end_date}")
        print(f"💰 초기 자본: {stats.initial_capital:,.0f}원")
        print(f"💰 최종 자산: {stats.final_equity:,.0f}원")

        print(f"\n📈 수익률")
        print(f"  총 수익률: {stats.total_return_pct:+.2f}%")
        print(f"  CAGR: {stats.cagr:+.2f}%")

        print(f"\n📊 거래 통계")
        print(f"  총 거래 수: {stats.total_trades}")
        print(f"  승률: {stats.win_rate:.1f}% ({stats.winning_trades}승 / {stats.losing_trades}패)")
        print(f"  평균 수익: {stats.avg_win:,.0f}원")
        print(f"  평균 손실: {stats.avg_loss:,.0f}원")
        print(f"  손익비: {stats.profit_factor:.2f}")
        print(f"  평균 R 배수: {stats.avg_r_multiple:+.2f}R")

        print(f"\n⚠️ 리스크 지표")
        print(f"  최대 낙폭(MDD): {stats.max_drawdown_pct:.2f}% ({stats.max_drawdown_date})")
        print(f"  샤프 비율: {stats.sharpe_ratio:.2f}")

        print(f"\n📆 기간 통계")
        print(f"  평균 보유 기간: {stats.avg_holding_days:.1f}일")
        print(f"  최대 연속 승: {stats.max_consecutive_wins}회")
        print(f"  최대 연속 패: {stats.max_consecutive_losses}회")

    def export_trades_csv(self, filepath: str):
        """
        거래 내역 CSV 출력
        """
        if not self.trades:
            print("거래 내역이 없습니다.")
            return

        # 디렉토리 생성
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "종목코드", "진입일", "진입가", "청산일", "청산가",
                "수량", "청산사유", "손익(원)", "수익률(%)", "R배수"
            ])
            for t in self.trades:
                writer.writerow([
                    t.ticker,
                    t.entry_date,
                    f"{t.entry_price:.0f}",
                    t.exit_date,
                    f"{t.exit_price:.0f}",
                    t.shares,
                    t.exit_reason,
                    f"{t.pnl:.0f}",
                    f"{t.pnl_pct:.2f}",
                    f"{t.r_multiple:.2f}",
                ])

        print(f"거래 내역 저장: {filepath}")

    def export_equity_csv(self, filepath: str):
        """
        자산 곡선 CSV 출력
        """
        if not self.daily_records:
            print("일별 기록이 없습니다.")
            return

        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["날짜", "총자산", "현금", "포지션수", "리스크"])
            for r in self.daily_records:
                writer.writerow([
                    r.date,
                    f"{r.equity:.0f}",
                    f"{r.cash:.0f}",
                    r.position_count,
                    f"{r.total_risk:.0f}",
                ])

        print(f"자산 곡선 저장: {filepath}")
