"""
RsiSwingStrategy - RSI 역추세 스윙 전략 (눌림목/과매도)

상승 추세 중 과매도 구간을 공략하는 역추세 전략입니다.

진입 조건:
- 추세 필터: 현재가 > 200일 이동평균 (장기 상승 추세)
- 진입 시그널: RSI(14) < 30 (과매도)

청산 조건:
- 목표 청산: RSI(14) > 70 (과매수 도달)
- 시간 청산: 진입 후 10거래일(영업일 아님, 단순 경과일) 경과 시 무조건 청산
- 손절: 초기 진입가 대비 ATR(20) * 2.5 하락 시 (안전장치)
"""

from typing import Optional
from datetime import datetime

from app.backtest.strategies.base import BaseStrategy, SignalData


class RsiSwingStrategy(BaseStrategy):
    """
    RSI(14) 역추세 스윙 전략
    
    장기 상승 추세(200MA 위)에 있는 종목이 일시적 과매도(RSI < 30)에 빠졌을 때 매수하여
    단기간 내 반등(RSI > 70)을 노리는 전략입니다.
    
    특징:
    - 높은 승률 (일반적으로 60~70%)
    - 짧은 보유 기간 (평균 3~5일, 최대 10일)
    - 회전율이 높음
    """

    # 전략 파라미터
    RSI_PERIOD = 14
    RSI_ENTRY_THRESHOLD = 45  # 절충안
    RSI_EXIT_THRESHOLD = 70   
    MAX_HOLDING_DAYS = 10     
    
    ATR_STOP_MULTIPLIER = 2.5 

    @property
    def name(self) -> str:
        return "RSI 스윙 (중기 눌림목)"

    def check_entry_signal(
        self,
        ticker: str,
        data: SignalData,
    ) -> bool:
        """
        진입 시그널 확인
        
        조건:
        1. 중기 추세: 종가 > 60MA
        2. 눌림목: RSI(14) < 45
        """
        if not data.ma60 or not data.rsi14:
            return False

        # 조건 1: 중기 상승 추세 (60일선 위)
        is_uptrend = data.close > data.ma60

        # 조건 2: 적당한 눌림목 (RSI 45 미만)
        is_oversold = data.rsi14 < self.RSI_ENTRY_THRESHOLD

        return is_uptrend and is_oversold

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
        
        우선순위:
        1. 손절 (안전장치)
        2. 시간 청산 (10일 경과)
        3. RSI 과매수 청산 (목표 달성)
        """
        # 1. 안전장치 손절
        if data.close <= initial_stop:
            return "STOP_LOSS"

        # 2. 시간 청산 (보유 기간 초과)
        days_held = self._calculate_days_held(entry_date, data.date)
        if days_held >= self.MAX_HOLDING_DAYS:
            return "TIME_EXIT"

        # 3. 목표 달성 (RSI 과매수)
        if data.rsi14 and data.rsi14 > self.RSI_EXIT_THRESHOLD:
            return "RSI_TARGET"

        return None

    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
    ) -> float:
        """손절가 = 진입가 - ATR * 2.5"""
        return entry_price - (atr * self.ATR_STOP_MULTIPLIER)

    def calculate_position_size(
        self,
        capital: float,
        risk_pct: float,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        """포지션 크기 (1% 리스크)"""
        if entry_price <= stop_loss:
            return 0

        r_unit = entry_price - stop_loss
        risk_amount = capital * risk_pct
        shares = int(risk_amount / r_unit)

        return max(0, shares)

    def _calculate_days_held(self, entry_date_str: str, current_date_str: str) -> int:
        """두 날짜 사이의 일수 계산"""
        try:
            d1 = datetime.strptime(entry_date_str, "%Y-%m-%d")
            d2 = datetime.strptime(current_date_str, "%Y-%m-%d")
            return (d2 - d1).days
        except ValueError:
            return 0
