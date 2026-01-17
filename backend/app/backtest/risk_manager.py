"""
RiskManager - 리스크 관리자

포지션 사이징, 총 리스크 관리, 리스크 감축/복구 로직을 담당합니다.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskState:
    """
    리스크 상태 추적
    
    Attributes:
        consecutive_losses: 연속 손절 횟수
        peak_equity: 최고 자산
        is_reduced: 감축 모드 여부
        reduced_trades_remaining: 감축 적용 남은 거래 수
        winning_exits_since_reduction: 감축 후 정상 청산 횟수
        r_gained_since_reduction: 감축 후 획득 R
    """
    consecutive_losses: int = 0
    peak_equity: float = 0.0
    is_reduced: bool = False
    reduced_trades_remaining: int = 0
    winning_exits_since_reduction: int = 0
    r_gained_since_reduction: float = 0.0


class RiskManager:
    """
    리스크 관리자
    
    전략 문서의 리스크 관리 규칙을 구현합니다:
    - 기본 리스크: 1%
    - 총 리스크 상한: 3~4%
    - 감축 트리거: 3연속 손절 or -7% 드로다운
    - 감축 규칙: 다음 3회 거래 리스크 50%
    - 복구 조건: +2R 이상 or 정상 청산 2회
    """

    # 기본 설정
    DEFAULT_RISK_PCT = 0.01       # 기본 리스크 1%
    REDUCED_RISK_PCT = 0.005      # 감축 리스크 0.5%
    MAX_PORTFOLIO_RISK = 0.04     # 총 리스크 상한 4%

    # 감축 트리거
    CONSECUTIVE_LOSS_TRIGGER = 3  # 연속 손절 3회
    DRAWDOWN_TRIGGER = 0.07       # 드로다운 7%

    # 복구 조건
    REDUCED_TRADES_COUNT = 3      # 감축 적용 거래 수
    RECOVERY_R_THRESHOLD = 2.0    # 복구 필요 R
    RECOVERY_WINS_THRESHOLD = 2   # 복구 필요 정상 청산 수

    def __init__(
        self,
        base_risk_pct: float = DEFAULT_RISK_PCT,
        max_portfolio_risk: float = MAX_PORTFOLIO_RISK,
    ):
        """
        리스크 관리자 초기화
        
        Args:
            base_risk_pct: 기본 리스크 비율
            max_portfolio_risk: 총 리스크 상한
        """
        self.base_risk_pct = base_risk_pct
        self.max_portfolio_risk = max_portfolio_risk
        self.state = RiskState()

    @property
    def current_risk_pct(self) -> float:
        """현재 적용되는 리스크 비율"""
        if self.state.is_reduced:
            return self.REDUCED_RISK_PCT
        return self.base_risk_pct

    def update_peak_equity(self, equity: float):
        """최고 자산 업데이트"""
        if equity > self.state.peak_equity:
            self.state.peak_equity = equity

    def check_drawdown(self, current_equity: float) -> float:
        """
        드로다운 계산
        
        Returns:
            드로다운 비율 (0.07 = 7%)
        """
        if self.state.peak_equity == 0:
            return 0.0
        return (self.state.peak_equity - current_equity) / self.state.peak_equity

    def can_take_risk(
        self,
        current_portfolio_risk: float,
        new_position_risk: float,
    ) -> bool:
        """
        신규 포지션 진입 가능 여부 (총 리스크 체크)
        
        Args:
            current_portfolio_risk: 현재 포트폴리오 리스크 비율
            new_position_risk: 신규 포지션 리스크 비율
            
        Returns:
            True: 진입 가능
            False: 리스크 상한 초과
        """
        total_risk = current_portfolio_risk + new_position_risk
        return total_risk <= self.max_portfolio_risk

    def on_trade_exit(
        self,
        is_stop_loss: bool,
        r_multiple: float,
        current_equity: float,
    ):
        """
        거래 청산 시 호출
        
        Args:
            is_stop_loss: 손절 여부
            r_multiple: R 배수
            current_equity: 현재 자산
        """
        if is_stop_loss:
            self.state.consecutive_losses += 1
            # 감축 모드 중 손절은 R 감소
            if self.state.is_reduced:
                self.state.r_gained_since_reduction += r_multiple
        else:
            self.state.consecutive_losses = 0
            # 감축 모드 중 정상 청산
            if self.state.is_reduced:
                self.state.winning_exits_since_reduction += 1
                self.state.r_gained_since_reduction += r_multiple

        # 감축 모드 중 거래 차감
        if self.state.is_reduced and self.state.reduced_trades_remaining > 0:
            self.state.reduced_trades_remaining -= 1

        # 감축 트리거 체크
        self._check_reduction_trigger(current_equity)

        # 복구 체크
        self._check_recovery()

    def _check_reduction_trigger(self, current_equity: float):
        """감축 트리거 확인"""
        if self.state.is_reduced:
            return  # 이미 감축 모드

        # 트리거 1: 연속 3회 손절
        if self.state.consecutive_losses >= self.CONSECUTIVE_LOSS_TRIGGER:
            self._activate_reduction("CONSECUTIVE_LOSSES")
            return

        # 트리거 2: -7% 드로다운
        drawdown = self.check_drawdown(current_equity)
        if drawdown >= self.DRAWDOWN_TRIGGER:
            self._activate_reduction("DRAWDOWN")

    def _activate_reduction(self, reason: str):
        """감축 모드 활성화"""
        self.state.is_reduced = True
        self.state.reduced_trades_remaining = self.REDUCED_TRADES_COUNT
        self.state.winning_exits_since_reduction = 0
        self.state.r_gained_since_reduction = 0.0
        print(f"[RiskManager] 리스크 감축 활성화: {reason}")
        print(f"  - 다음 {self.REDUCED_TRADES_COUNT}회 거래 리스크: {self.REDUCED_RISK_PCT*100}%")

    def _check_recovery(self):
        """복구 조건 확인"""
        if not self.state.is_reduced:
            return

        # 복구 조건 1: +2R 이상 회복
        if self.state.r_gained_since_reduction >= self.RECOVERY_R_THRESHOLD:
            self._deactivate_reduction("R_RECOVERY")
            return

        # 복구 조건 2: 정상 청산 2회
        if self.state.winning_exits_since_reduction >= self.RECOVERY_WINS_THRESHOLD:
            self._deactivate_reduction("WINS_RECOVERY")
            return

        # 감축 거래 수 소진
        if self.state.reduced_trades_remaining <= 0:
            self._deactivate_reduction("TRADES_EXHAUSTED")

    def _deactivate_reduction(self, reason: str):
        """감축 모드 해제"""
        self.state.is_reduced = False
        self.state.consecutive_losses = 0
        print(f"[RiskManager] 리스크 복구: {reason}")
        print(f"  - 기본 리스크로 복귀: {self.base_risk_pct*100}%")

    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        """
        포지션 크기 계산
        
        Args:
            capital: 사용 가능 자본
            entry_price: 진입가
            stop_loss: 손절가
            
        Returns:
            매수 수량 (정수)
        """
        if entry_price <= stop_loss:
            return 0

        risk_per_share = entry_price - stop_loss
        risk_amount = capital * self.current_risk_pct
        shares = int(risk_amount / risk_per_share)

        return max(0, shares)

    def get_state_summary(self) -> dict:
        """리스크 상태 요약"""
        return {
            "current_risk_pct": self.current_risk_pct,
            "is_reduced": self.state.is_reduced,
            "consecutive_losses": self.state.consecutive_losses,
            "reduced_trades_remaining": self.state.reduced_trades_remaining,
        }
