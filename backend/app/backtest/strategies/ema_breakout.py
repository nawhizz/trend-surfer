"""
EmaBreakoutStrategy - EMA 정배열 + 20일 신고가 돌파 전략

지수이동평균(EMA) 기반의 추세추종 전략입니다.

진입 조건:
- 시장 필터: KOSPI > 60MA AND KOSDAQ > 60MA
- 종목 필터: EMA 정배열 (20EMA > 50EMA > 120EMA)
- 진입 시그널: 종가 > 20일 최고가

청산 조건:
- 손절: 종가 < 초기 손절가 (진입가 - ATR*2.5)
- 트레일링: 종가 < 최고종가 - ATR*3.0
- 50EMA 이탈: 종가 < 50EMA
"""

from typing import Optional

from app.backtest.strategies.base import BaseStrategy, SignalData
from app.services.market_filter import market_filter


class EmaBreakoutStrategy(BaseStrategy):
    """
    EMA 정배열 + 20일 신고가 돌파 전략
    
    지수이동평균(Exponential Moving Average) 기반 추세추종 전략입니다.
    - 정배열: 20EMA > 50EMA > 120EMA (200EMA → 120EMA 완화)
    - 청산: 50EMA 하향 이탈 (20EMA → 50EMA 완화)
    """

    # 전략 파라미터
    ATR_STOP_MULTIPLIER = 2.5      # 초기 손절 ATR 배수
    ATR_TRAILING_MULTIPLIER = 3.0  # 트레일링 스탑 ATR 배수

    @property
    def name(self) -> str:
        return "EMA 정배열 + 20일 신고가 돌파"

    def check_market_filter(self, date: str) -> bool:
        """
        시장 필터 확인
        
        KOSPI > 60MA AND KOSDAQ > 60MA
        """
        return market_filter.is_bullish(date)

    def check_entry_signal(
        self,
        ticker: str,
        data: SignalData,
    ) -> bool:
        """
        진입 시그널 확인
        
        조건:
        1. EMA 정배열: 20EMA > 50EMA > 120EMA
        2. 20일 신고가 돌파: 종가 > HIGH(20)
        """
        # 필수 지표 확인
        if not all([data.ema20, data.ema50, data.ema120, data.high20]):
            return False

        # 조건 1: EMA 정배열 (120일선 사용)
        is_aligned = data.ema20 > data.ema50 > data.ema120

        # 조건 2: 20일 신고가 돌파
        is_breakout = data.close > data.high20

        return is_aligned and is_breakout

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
        
        OR 조건으로 하나라도 만족하면 청산:
        1. 손절: 종가 < 초기 손절가
        2. 트레일링 스탑: 종가 < 최고종가 - ATR*3.0
        3. 50EMA 이탈: 종가 < 50EMA
        """
        # 조건 1: 초기 손절
        if data.close <= initial_stop:
            return "STOP_LOSS"

        # 조건 2: 트레일링 스탑
        if data.atr20:
            trailing_stop = highest_close - (data.atr20 * self.ATR_TRAILING_MULTIPLIER)
            if data.close <= trailing_stop:
                return "TRAILING_STOP"

        # 조건 3: 50EMA 하향 이탈
        if data.ema50 and data.close < data.ema50:
            return "EMA_EXIT"

        return None

    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
    ) -> float:
        """
        초기 손절가 계산
        
        손절가 = 진입가 - ATR(20) × 2.5
        """
        return entry_price - (atr * self.ATR_STOP_MULTIPLIER)

    def calculate_position_size(
        self,
        capital: float,
        risk_pct: float,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        """
        포지션 크기 계산
        
        매수 수량 = (자본 × 리스크%) ÷ 1R
        1R = 진입가 - 손절가
        """
        if entry_price <= stop_loss:
            return 0

        r_unit = entry_price - stop_loss
        risk_amount = capital * risk_pct
        shares = int(risk_amount / r_unit)

        return max(0, shares)
