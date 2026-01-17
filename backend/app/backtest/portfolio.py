"""
Portfolio - 포트폴리오 및 포지션 관리

백테스트 중 자산, 현금, 포지션, 거래 내역을 관리합니다.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    """
    개별 포지션 (보유 종목)
    
    Attributes:
        ticker: 종목 코드
        entry_date: 진입일 (YYYY-MM-DD)
        entry_price: 진입가 (익일 시가)
        shares: 보유 수량
        initial_stop: 초기 손절가 (진입가 - ATR*배수)
        highest_close: 보유 중 최고 종가 (트레일링 스탑용)
        atr_at_entry: 진입 시점 ATR 값
        risk_amount: 이 포지션의 리스크 금액 (원)
    """
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    highest_close: float
    atr_at_entry: float
    risk_amount: float = 0.0

    @property
    def cost(self) -> float:
        """매수 금액"""
        return self.entry_price * self.shares

    def update_highest_close(self, close: float):
        """최고 종가 업데이트 (상승 시에만)"""
        if close > self.highest_close:
            self.highest_close = close

    def calculate_pnl(self, current_price: float) -> float:
        """현재 손익 계산"""
        return (current_price - self.entry_price) * self.shares

    def calculate_pnl_pct(self, current_price: float) -> float:
        """현재 손익률 계산"""
        return (current_price - self.entry_price) / self.entry_price * 100


@dataclass
class Trade:
    """
    완료된 거래 기록
    
    Attributes:
        ticker: 종목 코드
        entry_date: 진입일
        entry_price: 진입가
        exit_date: 청산일
        exit_price: 청산가
        shares: 수량
        exit_reason: 청산 사유 (STOP_LOSS, TRAILING, MA_EXIT 등)
        pnl: 손익 (원)
        pnl_pct: 손익률 (%)
        r_multiple: R 배수 (손절 기준 손익)
    """
    ticker: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    exit_reason: str
    pnl: float
    pnl_pct: float
    r_multiple: float


@dataclass
class DailyRecord:
    """
    일별 자산 기록
    
    Attributes:
        date: 날짜
        equity: 총 자산 (현금 + 보유 포지션 평가액)
        cash: 현금
        position_count: 보유 포지션 수
        total_risk: 총 포트폴리오 리스크
    """
    date: str
    equity: float
    cash: float
    position_count: int
    total_risk: float


class Portfolio:
    """
    포트폴리오 관리자
    
    자산, 현금, 포지션, 거래 내역을 관리합니다.
    """

    def __init__(self, initial_capital: float):
        """
        포트폴리오 초기화
        
        Args:
            initial_capital: 초기 자본금 (원)
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: list[Position] = []
        self.trades: list[Trade] = []
        self.daily_records: list[DailyRecord] = []

    @property
    def position_value(self) -> float:
        """보유 포지션 평가액 (시가 기준, 현재 가격 필요 시 별도 계산)"""
        return sum(p.cost for p in self.positions)

    @property
    def equity(self) -> float:
        """총 자산 (현금 + 포지션 매입가 기준)"""
        return self.cash + self.position_value

    @property
    def total_risk(self) -> float:
        """총 포트폴리오 리스크 (원)"""
        return sum(p.risk_amount for p in self.positions)

    @property
    def total_risk_pct(self) -> float:
        """총 포트폴리오 리스크 비율"""
        if self.equity == 0:
            return 0.0
        return self.total_risk / self.equity

    def get_position(self, ticker: str) -> Optional[Position]:
        """특정 종목의 포지션 조회"""
        for p in self.positions:
            if p.ticker == ticker:
                return p
        return None

    def has_position(self, ticker: str) -> bool:
        """특정 종목 보유 여부"""
        return self.get_position(ticker) is not None

    def open_position(
        self,
        ticker: str,
        date: str,
        price: float,
        shares: int,
        stop_loss: float,
        atr: float,
    ):
        """
        포지션 진입
        
        Args:
            ticker: 종목 코드
            date: 진입일
            price: 진입가
            shares: 수량
            stop_loss: 손절가
            atr: ATR 값
        """
        cost = price * shares
        if cost > self.cash:
            raise ValueError(f"현금 부족: 필요 {cost:,.0f}, 보유 {self.cash:,.0f}")

        # 리스크 금액 = (진입가 - 손절가) × 수량
        risk_amount = (price - stop_loss) * shares

        position = Position(
            ticker=ticker,
            entry_date=date,
            entry_price=price,
            shares=shares,
            initial_stop=stop_loss,
            highest_close=price,  # 진입 시 최고가 = 진입가
            atr_at_entry=atr,
            risk_amount=risk_amount,
        )

        self.positions.append(position)
        self.cash -= cost

    def close_position(
        self,
        ticker: str,
        date: str,
        price: float,
        reason: str,
    ) -> Optional[Trade]:
        """
        포지션 청산
        
        Args:
            ticker: 종목 코드
            date: 청산일
            price: 청산가
            reason: 청산 사유
            
        Returns:
            완료된 거래 기록
        """
        position = self.get_position(ticker)
        if not position:
            return None

        # 손익 계산
        pnl = (price - position.entry_price) * position.shares
        pnl_pct = (price - position.entry_price) / position.entry_price * 100

        # R 배수 계산 (1R = 진입가 - 손절가)
        r_unit = position.entry_price - position.initial_stop
        r_multiple = (price - position.entry_price) / r_unit if r_unit > 0 else 0

        # 거래 기록 생성
        trade = Trade(
            ticker=ticker,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            exit_date=date,
            exit_price=price,
            shares=position.shares,
            exit_reason=reason,
            pnl=pnl,
            pnl_pct=pnl_pct,
            r_multiple=r_multiple,
        )

        # 현금 회수
        self.cash += price * position.shares

        # 포지션 제거
        self.positions.remove(position)

        # 거래 내역 추가
        self.trades.append(trade)

        return trade

    def record_daily(self, date: str, prices: dict[str, float]):
        """
        일별 자산 기록
        
        Args:
            date: 날짜
            prices: 종목별 현재가 {ticker: price}
        """
        # 포지션 평가액 계산
        position_value = 0.0
        for p in self.positions:
            current_price = prices.get(p.ticker, p.entry_price)
            position_value += current_price * p.shares

        equity = self.cash + position_value

        record = DailyRecord(
            date=date,
            equity=equity,
            cash=self.cash,
            position_count=len(self.positions),
            total_risk=self.total_risk,
        )
        self.daily_records.append(record)

    def get_stats(self) -> dict:
        """
        기본 통계 반환
        
        Returns:
            통계 딕셔너리
        """
        if not self.trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_return_pct": 0.0,
            }

        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in self.trades)

        return {
            "total_trades": len(self.trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(self.trades) * 100,
            "total_pnl": total_pnl,
            "total_return_pct": total_pnl / self.initial_capital * 100,
        }
