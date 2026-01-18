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
    ATR_OVERHEAT_THRESHOLD = 0.08  # ATR/종가 > 8% 이면 과열
    
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
        if not market_filter.is_bullish(date):
            return False
        
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
