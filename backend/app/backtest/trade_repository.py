"""
TradeRepository - 백테스트 매매 기록 DB 저장

백테스트 세션 생성, 매수/매도 기록 저장, 포지션 관리를 담당합니다.
Supabase에 직접 INSERT하여 실제 매매처럼 기록을 남깁니다.
"""

from datetime import datetime
from typing import Optional
import uuid

from app.db.client import supabase


class TradeRepository:
    """
    백테스트 매매 기록 저장소
    
    DB 테이블:
    - backtest_sessions: 백테스트 세션 정보
    - backtest_trades: 매수/매도 기록
    - backtest_positions: 보유 중인 포지션
    """

    def __init__(self):
        self.session_id: Optional[str] = None

    def create_session(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
        risk_per_trade: float = 0.01,
    ) -> str:
        """
        새 백테스트 세션 생성
        
        Returns:
            session_id (UUID)
        """
        session_data = {
            "strategy_name": strategy_name,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "risk_per_trade": risk_per_trade,
        }
        
        response = supabase.table("backtest_sessions").insert(session_data).execute()
        
        if response.data:
            self.session_id = response.data[0]["id"]
            return self.session_id
        else:
            raise Exception("세션 생성 실패")

    def record_buy(
        self,
        ticker: str,
        trade_date: str,
        price: float,
        shares: int,
        stop_loss: float,
        atr: float,
    ):
        """
        매수 기록 저장
        
        1. backtest_trades에 BUY 레코드 추가
        2. backtest_positions에 포지션 추가
        """
        if not self.session_id:
            raise Exception("세션이 생성되지 않았습니다")

        # 1. 매수 거래 기록
        trade_data = {
            "session_id": self.session_id,
            "ticker": ticker,
            "trade_type": "BUY",
            "trade_date": trade_date,
            "price": price,
            "shares": shares,
            "stop_loss": stop_loss,
            "atr_at_entry": atr,
        }
        supabase.table("backtest_trades").insert(trade_data).execute()

        # 2. 포지션 추가
        position_data = {
            "session_id": self.session_id,
            "ticker": ticker,
            "entry_date": trade_date,
            "entry_price": price,
            "shares": shares,
            "stop_loss": stop_loss,
            "highest_close": price,  # 진입 시 최고가 = 진입가
            "atr_at_entry": atr,
        }
        supabase.table("backtest_positions").upsert(position_data).execute()

    def record_sell(
        self,
        ticker: str,
        trade_date: str,
        price: float,
        shares: int,
        exit_reason: str,
        pnl: float,
        pnl_pct: float,
        r_multiple: float,
    ):
        """
        매도 기록 저장
        
        1. backtest_trades에 SELL 레코드 추가
        2. backtest_positions에서 포지션 삭제
        """
        if not self.session_id:
            raise Exception("세션이 생성되지 않았습니다")

        # 1. 매도 거래 기록
        trade_data = {
            "session_id": self.session_id,
            "ticker": ticker,
            "trade_type": "SELL",
            "trade_date": trade_date,
            "price": price,
            "shares": shares,
            "exit_reason": exit_reason,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "r_multiple": r_multiple,
        }
        supabase.table("backtest_trades").insert(trade_data).execute()

        # 2. 포지션 삭제
        supabase.table("backtest_positions").delete().eq(
            "session_id", self.session_id
        ).eq("ticker", ticker).execute()

    def update_highest_close(self, ticker: str, highest_close: float):
        """
        포지션의 최고 종가 업데이트 (트레일링 스탑용)
        """
        if not self.session_id:
            return

        supabase.table("backtest_positions").update(
            {"highest_close": highest_close}
        ).eq("session_id", self.session_id).eq("ticker", ticker).execute()

    def get_positions(self) -> list[dict]:
        """
        현재 보유 중인 포지션 조회
        """
        if not self.session_id:
            return []

        response = (
            supabase.table("backtest_positions")
            .select("*")
            .eq("session_id", self.session_id)
            .execute()
        )
        return response.data or []

    def get_position(self, ticker: str) -> Optional[dict]:
        """
        특정 종목 포지션 조회
        """
        if not self.session_id:
            return None

        response = (
            supabase.table("backtest_positions")
            .select("*")
            .eq("session_id", self.session_id)
            .eq("ticker", ticker)
            .execute()
        )
        return response.data[0] if response.data else None

    def has_position(self, ticker: str) -> bool:
        """
        특정 종목 보유 여부
        """
        return self.get_position(ticker) is not None

    def get_trades(self) -> list[dict]:
        """
        세션의 모든 거래 기록 조회
        """
        if not self.session_id:
            return []

        response = (
            supabase.table("backtest_trades")
            .select("*")
            .eq("session_id", self.session_id)
            .order("trade_date")
            .execute()
        )
        return response.data or []

    def get_session_summary(self) -> dict:
        """
        세션 요약 정보 조회
        """
        trades = self.get_trades()
        sells = [t for t in trades if t["trade_type"] == "SELL"]

        total_pnl = sum(t["pnl"] or 0 for t in sells)
        wins = len([t for t in sells if (t["pnl"] or 0) > 0])
        losses = len([t for t in sells if (t["pnl"] or 0) <= 0])

        return {
            "session_id": self.session_id,
            "total_trades": len(sells),
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": (wins / len(sells) * 100) if sells else 0,
            "total_pnl": total_pnl,
        }

    def cleanup_session(self):
        """
        세션 정리 (포지션 테이블 비우기)
        """
        if self.session_id:
            supabase.table("backtest_positions").delete().eq(
                "session_id", self.session_id
            ).execute()
