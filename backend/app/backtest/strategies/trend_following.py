"""
TrendFollowingStrategy - 추세추종 전략

20일 신고가 돌파 + 50EMA 필터 + ATR 트레일링 기반 추세추종 전략입니다.

진입 조건 (모두 충족):
1. 종가 > 20일 최고가 (신고가 돌파)
2. 50EMA 기울기 ≥ -0.2 (ATR 정규화, 구조 필터)
3. ATR20 / 종가 ≤ 8% (ATR 과열 아님)
4. 시장 구조 OK (지수 EMA50 하락 아님)

청산 조건 (하나라도 만족):
- 주력: 종가 < (보유 중 최고가 - 2.5 × ATR)
- 보조: 종가 < 50EMA AND (기울기 < -0.3 OR 2일 연속 이탈)

손절: 진입가 - 2 × ATR
"""

from typing import Optional

from app.backtest.strategies.base import BaseStrategy, SignalData
from app.services.market_filter import market_filter


class TrendFollowingStrategy(BaseStrategy):
    """
    추세추종 전략 (20일 신고가 + 50EMA 필터 + ATR 트레일링)
    
    이 전략은 "맞히는 전략이 아니라 살아남아 크게 먹는 전략"입니다.
    손실 분포는 고정하고, 수익 분포의 상단만 확장합니다.
    """

    # ========================================
    # 전략 파라미터
    # ========================================
    
    # 손절 및 트레일링 스탑 ATR 배수
    ATR_STOP_MULTIPLIER = 2.0       # 초기 손절: 진입가 - 2 × ATR
    ATR_TRAILING_MULTIPLIER = 2.5   # 트레일링 스탑: 최고가 - 2.5 × ATR
    
    # EMA 기울기 임계값 (ATR 정규화)
    EMA_SLOPE_ENTRY_THRESHOLD = -0.2   # 진입 허용 기울기 하한
    EMA_SLOPE_EXIT_THRESHOLD = -0.3    # 청산 조건 기울기 하한
    
    # ATR 과열 임계값
    # ATR 과열 임계값
    # ATR 과열 임계값
    ATR_OVERHEAT_THRESHOLD = 0.15  # ATR/종가 > 15% 이면 과열 (기존 10%에서 상향)
    
    # 재진입 쿨타임 (청산 후 재진입 대기 일수)
    RE_ENTRY_COOLDOWN = 3
    
    # EMA 연속 이탈 일수
    EMA_BELOW_DAYS_THRESHOLD = 2

    @property
    def name(self) -> str:
        return "추세추종 (20일 신고가 + 50EMA 필터)"

    # ========================================
    # 시장 필터
    # ========================================

    def check_market_filter(self, date: str) -> bool:
        """
        시장 필터 확인
        
        조건:
        1. KOSPI > 60MA AND KOSDAQ > 60MA
        2. 지수 EMA50 기울기 ≥ -0.2 (구조 붕괴 아님)
        """
        # 기본 시장 필터: 지수가 60MA 위에 있는지
        # 기본 시장 필터: 지수가 60MA 위에 있는지
        # [튜닝] 2026-01-18: 진입 기회 확대를 위해 MA60 필터 제거 (EMA 구조 필터만 사용)
        # if not market_filter.is_bullish(date):
        #     return False
        
        # 추가 필터: 지수 EMA50 구조 확인
        if not market_filter.is_index_structure_ok(date, self.EMA_SLOPE_ENTRY_THRESHOLD):
            return False
        
        return True

    # ========================================
    # 진입 시그널
    # ========================================

    def check_entry_signal(
        self,
        ticker: str,
        data: SignalData,
    ) -> bool:
        """
        진입 시그널 확인
        
        조건 (모두 충족):
        1. 20일 신고가 돌파: 종가 > HIGH(20)
        2. 50EMA 기울기 필터: slope ≥ -0.2
        3. ATR 과열 아님: ATR20 / 종가 ≤ 8%
        """
        # 필수 지표 확인
        if not all([data.high20, data.atr20, data.ema50_slope]):
            return False
        
        # 조건 1: 20일 신고가 돌파
        is_breakout = data.close > data.high20
        if not is_breakout:
            return False
        
        # 조건 2: 50EMA 기울기 필터 (구조 상승 또는 보합)
        is_structure_ok = data.ema50_slope >= self.EMA_SLOPE_ENTRY_THRESHOLD
        if not is_structure_ok:
            return False
        
        # 조건 3: ATR 과열 아님
        atr_ratio = data.atr20 / data.close
        is_not_overheated = atr_ratio <= self.ATR_OVERHEAT_THRESHOLD
        if not is_not_overheated:
            return False
        
        return True

    # ========================================
    # 청산 시그널
    # ========================================

    def check_exit_signal(
        self,
        ticker: str,
        data: SignalData,
        entry_price: float,
        entry_date: str,
        highest_close: float,
        initial_stop: float,
    ) -> Optional[str]:
        """
        청산 시그널 확인
        
        조건 (하나라도 만족):
        1. 초기 손절: 종가 ≤ 초기 손절가
        2. ATR 트레일링: 종가 < (보유 중 최고 종가 - 2.5 × ATR)
        3. 보조 청산: 종가 < 50EMA AND (기울기 < -0.3 OR 2일 연속 이탈)
        """
        # 조건 1: 초기 손절
        if data.close <= initial_stop:
            return "STOP_LOSS"
        
        # 조건 2: ATR 트레일링 스탑
        if data.atr20:
            trailing_stop = highest_close - (data.atr20 * self.ATR_TRAILING_MULTIPLIER)
            if data.close < trailing_stop:
                return "TRAILING_STOP"
        
        # 조건 3: 보조 청산 (50EMA 구조 붕괴)
        if data.ema50 and data.close < data.ema50:
            # 기울기가 급락하면 즉시 청산
            if data.ema50_slope and data.ema50_slope < self.EMA_SLOPE_EXIT_THRESHOLD:
                return "EMA_STRUCTURE_EXIT"
            
            # TODO: 2일 연속 이탈 확인은 추후 구현
            # 현재는 기울기 조건만 사용
        
        return None

    # ========================================
    # 손절가 계산
    # ========================================

    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
    ) -> float:
        """
        초기 손절가 계산
        
        손절가 = 진입가 - ATR(20) × 2
        """
        return entry_price - (atr * self.ATR_STOP_MULTIPLIER)

    # ========================================
    # 포지션 사이징
    # ========================================

    def calculate_position_size(
        self,
        capital: float,
        risk_pct: float,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        """
        포지션 크기 계산 (1R 기반)
        
        1R = 계좌 × r% (기본 1%)
        1R₁ = 진입가 - 손절가 = ATR × 2
        매수 수량 = 1R ÷ 1R₁
        
        → 최대 손실 = 정확히 1R
        """
        if entry_price <= stop_loss:
            return 0
        
        # 1R: 리스크 금액 (계좌의 r%)
        risk_amount = capital * risk_pct
        
        # 1R₁: 주당 리스크 (진입가 - 손절가)
        r_unit = entry_price - stop_loss
        
        # 매수 수량
        shares = int(risk_amount / r_unit)
        
        return max(0, shares)

    # ========================================
    # 불타기 (Pyramiding)
    # ========================================

    # 불타기 파라미터
    PYRAMID_MFE_THRESHOLD = 1.0  # 기존 포지션 MFE >= +1R
    PYRAMID_MAX_TOTAL_RISK = 2.0  # 총 오픈 리스크 <= 2R
    PYRAMID_RISK_PER_ADD = 0.5   # 불타기당 최대 0.5R

    def check_pyramid_signal(
        self,
        ticker: str,
        data: SignalData,
        current_mfe_r: float,
        current_r_unit: float,
        new_r_unit: float,
        total_open_risk_r: float,
    ) -> bool:
        """
        불타기 시그널 확인
        
        조건 (모두 충족):
        1. 기존 포지션 MFE >= +1R
        2. 추가 진입의 손절폭(1R₂) < 기존 손절폭(1R₁)
        3. 10일 고점 돌파 또는 20일 고점 재갱신
        4. 총 오픈 리스크 <= 2R
        
        Args:
            ticker: 종목 코드
            data: 시그널 데이터
            current_mfe_r: 기존 포지션의 현재 MFE (R 단위)
            current_r_unit: 기존 포지션의 1R (손절폭)
            new_r_unit: 추가 진입 시 1R (새 손절폭)
            total_open_risk_r: 현재 총 오픈 리스크 (R 단위)
        
        Returns:
            True: 불타기 허용
            False: 불타기 금지
        """
        # 필수 지표 확인
        if not all([data.high10, data.high20, data.atr20]):
            return False
        
        # 조건 1: MFE >= +1R
        if current_mfe_r < self.PYRAMID_MFE_THRESHOLD:
            return False
        
        # 조건 2: 새 손절폭 < 기존 손절폭
        if new_r_unit >= current_r_unit:
            return False
        
        # 조건 3: 10일 또는 20일 고점 돌파
        is_high10_break = data.close > data.high10
        is_high20_break = data.close > data.high20
        if not (is_high10_break or is_high20_break):
            return False
        
        # 조건 4: 총 리스크 2R 이하
        if total_open_risk_r >= self.PYRAMID_MAX_TOTAL_RISK:
            return False
        
        return True

    def calculate_pyramid_size(
        self,
        capital: float,
        risk_pct: float,
        entry_price: float,
        stop_loss: float,
        total_open_risk_r: float,
    ) -> int:
        """
        불타기 포지션 크기 계산
        
        불타기 리스크 = min(0.5R, 2R - 현재 오픈 리스크)
        
        Args:
            capital: 사용 가능 자본
            risk_pct: 기본 리스크 비율 (1R)
            entry_price: 진입가
            stop_loss: 손절가
            total_open_risk_r: 현재 총 오픈 리스크 (R 단위)
        
        Returns:
            매수 수량 (정수)
        """
        if entry_price <= stop_loss:
            return 0
        
        # 불타기 리스크 계산
        remaining_risk_r = self.PYRAMID_MAX_TOTAL_RISK - total_open_risk_r
        pyramid_risk_r = min(self.PYRAMID_RISK_PER_ADD, remaining_risk_r)
        
        if pyramid_risk_r <= 0:
            return 0
        
        # 1R 금액
        one_r_amount = capital * risk_pct
        
        # 불타기 리스크 금액
        pyramid_risk_amount = one_r_amount * pyramid_risk_r
        
        # 주당 리스크
        r_unit = entry_price - stop_loss
        
        # 매수 수량
        shares = int(pyramid_risk_amount / r_unit)
        
        return max(0, shares)
