"""
BaseStrategy - 전략 기본 인터페이스

모든 백테스트 전략이 구현해야 하는 추상 클래스입니다.
새로운 전략을 추가하려면 이 클래스를 상속받아 구현하세요.

사용 예시:
    class MyStrategy(BaseStrategy):
        def check_entry_signal(self, ticker, date, data):
            # 진입 조건 구현
            return True
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SignalData:
    """
    전략에 전달되는 시장 데이터
    
    Attributes:
        date: 기준일 (YYYY-MM-DD)
        open: 시가
        high: 고가
        low: 저가
        close: 종가
        volume: 거래량
        ma20: 20일 이동평균
        ma60: 60일 이동평균
        ma120: 120일 이동평균
        ema20: 20일 지수이동평균
        ema50: 50일 지수이동평균
        ema200: 200일 지수이동평균
        atr20: 20일 ATR
        high10: 10일 최고 종가 (불타기 조건용)
        high20: 20일 최고 종가 (당일 제외)
        ema50_slope: 50EMA ATR 정규화 기울기 (구조 필터)
    """
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma120: Optional[float] = None
    ma200: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema120: Optional[float] = None
    ema200: Optional[float] = None
    atr20: Optional[float] = None
    rsi14: Optional[float] = None
    high10: Optional[float] = None       # 10일 최고가 (불타기용)
    high20: Optional[float] = None       # 20일 최고가 (신고가 돌파용)
    ema50_slope: Optional[float] = None  # 50EMA ATR 정규화 기울기


class BaseStrategy(ABC):
    """
    전략 기본 인터페이스
    
    모든 백테스트 전략은 이 클래스를 상속받아 구현해야 합니다.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """전략 이름"""
        pass

    @abstractmethod
    def check_entry_signal(
        self,
        ticker: str,
        data: SignalData,
    ) -> bool:
        """
        진입 시그널 확인
        
        Args:
            ticker: 종목 코드
            data: 시장 데이터
            
        Returns:
            True: 진입 시그널 발생
            False: 시그널 없음
        """
        pass

    @abstractmethod
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
        
        Args:
            ticker: 종목 코드
            data: 시장 데이터
            entry_price: 진입가
            entry_date: 진입일 (YYYY-MM-DD)
            highest_close: 보유 중 최고 종가
            initial_stop: 초기 손절가
            
        Returns:
            청산 사유 문자열 (예: "STOP_LOSS", "TRAILING", "MA_EXIT", "TIME_EXIT")
            None: 청산 시그널 없음 (포지션 유지)
        """
        pass

    @abstractmethod
    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
    ) -> float:
        """
        초기 손절가 계산
        
        Args:
            entry_price: 진입가
            atr: ATR 값
            
        Returns:
            손절가
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self,
        capital: float,
        risk_pct: float,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        """
        포지션 크기 계산 (주식 수)
        
        Args:
            capital: 사용 가능 자본
            risk_pct: 리스크 비율 (예: 0.01 = 1%)
            entry_price: 예상 진입가
            stop_loss: 손절가
            
        Returns:
            매수 수량 (정수)
        """
        pass

    def check_market_filter(self, date: str) -> bool:
        """
        시장 필터 확인 (선택적 오버라이드)
        
        기본 구현은 항상 True를 반환합니다.
        시장 상황에 따라 진입을 제한하려면 오버라이드하세요.
        
        Args:
            date: 기준일 (YYYY-MM-DD)
            
        Returns:
            True: 신규 진입 허용
            False: 신규 진입 금지
        """
        return True

    def on_entry(self, ticker: str, date: str, price: float, shares: int):
        """
        진입 시 콜백 (선택적 오버라이드)
        
        로깅이나 추가 처리에 사용할 수 있습니다.
        """
        pass

    def on_exit(self, ticker: str, date: str, price: float, shares: int, reason: str):
        """
        청산 시 콜백 (선택적 오버라이드)
        
        로깅이나 추가 처리에 사용할 수 있습니다.
        """
        pass
