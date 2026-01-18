"""
BacktestEngine - 백테스트 엔진

일별 시뮬레이션을 실행하여 전략을 백테스트합니다.
Strategy 패턴을 사용하여 다양한 전략을 플러그인처럼 교체할 수 있습니다.
매매 기록은 DB에 저장되어 실제 매매처럼 추적 가능합니다.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.db.client import supabase
from app.backtest.portfolio import Portfolio
from app.backtest.risk_manager import RiskManager
from app.backtest.strategies.base import BaseStrategy, SignalData
from app.backtest.trade_repository import TradeRepository


@dataclass
class PendingEntry:
    """
    익일 시가 진입 대기 항목
    
    오늘 진입 시그널이 발생하면 내일 시가에 실제 진입합니다.
    """
    ticker: str
    signal_date: str      # 시그널 발생일
    signal_close: float   # 시그널 발생 시 종가 (참고용)
    atr: float            # 시그널 발생 시 ATR (손절가 계산용)


class BacktestEngine:
    """
    백테스트 엔진
    
    전략을 주입받아 일별로 시뮬레이션을 실행합니다.
    모든 매수/매도는 DB에 기록됩니다.
    
    사용 예시:
        strategy = TrendFollowingStrategy()
        engine = BacktestEngine(strategy, initial_capital=100_000_000)
        result = engine.run("2020-01-01", "2025-12-31", ["005930"])
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 100_000_000,
        risk_per_trade: float = 0.01,
        max_portfolio_risk: float = 0.04,
        save_to_db: bool = True,
    ):
        """
        백테스트 엔진 초기화
        
        Args:
            strategy: 사용할 전략 (BaseStrategy 상속)
            initial_capital: 초기 자본금 (원)
            risk_per_trade: 거래당 리스크 비율 (기본 1%)
            max_portfolio_risk: 총 리스크 상한 (기본 4%)
            save_to_db: DB에 매매 기록 저장 여부 (기본 True)
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.portfolio = Portfolio(initial_capital)
        self.risk_manager = RiskManager(
            base_risk_pct=risk_per_trade,
            max_portfolio_risk=max_portfolio_risk,
        )
        self.risk_manager.update_peak_equity(initial_capital)
        
        # DB 저장 옵션
        self.save_to_db = save_to_db
        self.trade_repo = TradeRepository() if save_to_db else None
        
        # 익일 시가 진입 대기 목록
        self.pending_entries: list[PendingEntry] = []
        
        # 손절 발생 당일 재진입 금지를 위한 추적
        self.stopped_out_today: set[str] = set()

    def run(
        self,
        start_date: str,
        end_date: str,
        tickers: list[str],
        verbose: bool = True,
    ) -> dict:
        """
        백테스트 실행
        
        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            tickers: 대상 종목 리스트
            verbose: 상세 로그 출력 여부
            
        Returns:
            백테스트 결과 딕셔너리
        """
        if verbose:
            print("=" * 60)
            print(f"백테스트 시작: {self.strategy.name}")
            print(f"  기간: {start_date} ~ {end_date}")
            print(f"  종목 수: {len(tickers)}")
            print(f"  초기 자본: {self.portfolio.initial_capital:,.0f}원")
            print(f"  DB 저장: {'활성화' if self.save_to_db else '비활성화'}")
            print("=" * 60)

        # DB 세션 생성
        if self.save_to_db and self.trade_repo:
            session_id = self.trade_repo.create_session(
                strategy_name=self.strategy.name,
                start_date=start_date,
                end_date=end_date,
                initial_capital=self.initial_capital,
                risk_per_trade=self.risk_per_trade,
            )
            if verbose:
                print(f"세션 ID: {session_id}")

        # 거래일 목록 조회
        trading_days = self._get_trading_days(start_date, end_date)
        if verbose:
            print(f"거래일 수: {len(trading_days)}")

        # 종목별 데이터 캐시 (성능 최적화)
        data_cache = self._preload_data(tickers, start_date, end_date)

        # 일별 시뮬레이션
        for date in trading_days:
            self._process_day(date, tickers, data_cache, verbose)

        # 결과 정리
        result = self._generate_result(start_date, end_date, verbose)
        return result

    def _get_trading_days(self, start_date: str, end_date: str) -> list[str]:
        """거래일 목록 조회"""
        response = (
            supabase.table("daily_candles")
            .select("date")
            .eq("ticker", "KS11")
            .gte("date", start_date)
            .lte("date", end_date)
            .order("date")
            .execute()
        )
        if not response.data:
            return []
        return [row["date"] for row in response.data]

    def _preload_data(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
    ) -> dict:
        """종목별 데이터 미리 로드"""
        data_cache = {}

        for ticker in tickers:
            # 일봉 데이터 조회
            candles_resp = (
                supabase.table("daily_candles")
                .select("date, open, high, low, close, volume")
                .eq("ticker", ticker)
                .gte("date", start_date)
                .lte("date", end_date)
                .order("date")
                .execute()
            )

            # 지표 데이터 조회
            indicators_resp = (
                supabase.table("daily_technical_indicators")
                .select("date, indicator_type, params, value")
                .eq("ticker", ticker)
                .gte("date", start_date)
                .lte("date", end_date)
                .execute()
            )

            # 지표 데이터 정리
            indicators_map = {}
            for row in indicators_resp.data or []:
                date = row["date"]
                ind_type = row["indicator_type"]
                params = row["params"]
                value = row["value"]

                if date not in indicators_map:
                    indicators_map[date] = {}

                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except json.JSONDecodeError:
                        params = {}
                
                if isinstance(params, dict):
                    period = params.get("period", "")
                    ind_key = f"{ind_type}_{period}"
                else:
                    ind_key = ind_type

                indicators_map[date][ind_key] = value

            # SignalData로 변환
            ticker_data = {}
            for candle in candles_resp.data or []:
                date = candle["date"]
                indicators = indicators_map.get(date, {})

                signal_data = SignalData(
                    date=date,
                    open=float(candle["open"] or 0),
                    high=float(candle["high"] or 0),
                    low=float(candle["low"] or 0),
                    close=float(candle["close"] or 0),
                    volume=int(candle["volume"] or 0),
                    ma20=indicators.get("MA_20"),
                    ma60=indicators.get("MA_60"),
                    ma120=indicators.get("MA_120"),
                    ma200=indicators.get("MA_200"),
                    ema20=indicators.get("EMA_20"),
                    ema50=indicators.get("EMA_50"),
                    ema120=indicators.get("EMA_120"),
                    ema200=indicators.get("EMA_200"),
                    atr20=indicators.get("ATR_20"),
                    rsi14=indicators.get("RSI_14"),
                    high10=indicators.get("HIGH_10"),
                    high20=indicators.get("HIGH_20"),
                    ema50_slope=indicators.get("EMA_SLOPE_50"),
                )
                ticker_data[date] = signal_data

            data_cache[ticker] = ticker_data

        return data_cache

    def _process_day(
        self,
        date: str,
        tickers: list[str],
        data_cache: dict,
        verbose: bool,
    ):
        """하루 시뮬레이션 처리"""
        # 기본값 초기화 (에러 발생 시에도 사용)
        prices = {}
        
        try:
            # 1. 전일 손절 추적 초기화
            self.stopped_out_today.clear()

            # 2. 시장 필터 체크
            is_market_ok = self.strategy.check_market_filter(date)

            # 3. 대기 중인 진입 처리 (익일 시가)
            self._process_pending_entries(date, data_cache, is_market_ok, verbose)

            # 4. 기존 포지션 청산 체크
            self._process_exits(date, data_cache, verbose)

            # 5. 신규 진입 시그널 스캔
            if is_market_ok:
                self._scan_entry_signals(date, tickers, data_cache, verbose)

            # 6. 일별 기록용 가격 수집
            for ticker in tickers:
                data = data_cache.get(ticker, {}).get(date)
                if data:
                    prices[ticker] = data.close
        except Exception as e:
            if verbose:
                print(f"[{date}] 처리 중 에러: {e}")

        # 일별 기록 (에러 발생 여부와 무관하게 실행)
        self.portfolio.record_daily(date, prices)
        self.risk_manager.update_peak_equity(self.portfolio.equity)

    def _process_pending_entries(
        self,
        date: str,
        data_cache: dict,
        is_market_ok: bool,
        verbose: bool,
    ):
        """대기 중인 진입 처리 (익일 시가에 매수)"""
        processed = []
        
        for pending in self.pending_entries:
            ticker = pending.ticker
            data = data_cache.get(ticker, {}).get(date)
            
            if not data:
                processed.append(pending)
                continue
            
            if not is_market_ok:
                if verbose:
                    print(f"[{date}] 진입 취소 (시장 필터 OFF): {ticker}")
                processed.append(pending)
                continue
            
            if self.portfolio.has_position(ticker):
                processed.append(pending)
                continue
            
            # 익일 시가로 진입
            entry_price = data.open
            
            # 손절가 계산
            stop_loss = self.strategy.calculate_stop_loss(
                entry_price=entry_price,
                atr=pending.atr,
            )
            
            # 포지션 크기 계산
            shares = self.risk_manager.calculate_position_size(
                capital=self.portfolio.equity,
                entry_price=entry_price,
                stop_loss=stop_loss,
            )
            
            if shares <= 0:
                processed.append(pending)
                continue
            
            # 리스크 상한 체크
            new_risk = (entry_price - stop_loss) * shares
            new_risk_pct = new_risk / self.portfolio.equity
            
            if not self.risk_manager.can_take_risk(
                self.portfolio.total_risk_pct,
                new_risk_pct,
            ):
                if verbose:
                    print(f"[{date}] 진입 취소 (리스크 상한): {ticker}")
                processed.append(pending)
                continue
            
            # 현금 확인
            cost = entry_price * shares
            if cost > self.portfolio.cash:
                shares = int(self.portfolio.cash / entry_price)
                if shares <= 0:
                    processed.append(pending)
                    continue
            
            # 포지션 진입
            try:
                self.portfolio.open_position(
                    ticker=ticker,
                    date=date,
                    price=entry_price,
                    shares=shares,
                    stop_loss=stop_loss,
                    atr=pending.atr,
                )
                
                # DB에 매수 기록 저장
                if self.save_to_db and self.trade_repo:
                    self.trade_repo.record_buy(
                        ticker=ticker,
                        trade_date=date,
                        price=entry_price,
                        shares=shares,
                        stop_loss=stop_loss,
                        atr=pending.atr,
                    )
                
                if verbose:
                    print(f"[{date}] 매수: {ticker} @ {entry_price:,.0f} "
                          f"x {shares}주 (손절: {stop_loss:,.0f})")
            except ValueError as e:
                if verbose:
                    print(f"[{date}] 진입 실패: {ticker} - {e}")
            
            processed.append(pending)
        
        for p in processed:
            self.pending_entries.remove(p)

    def _process_exits(
        self,
        date: str,
        data_cache: dict,
        verbose: bool,
    ):
        """기존 포지션 청산 체크"""
        positions_to_close = []
        
        for position in self.portfolio.positions:
            ticker = position.ticker
            data = data_cache.get(ticker, {}).get(date)

            if not data:
                continue

            # 최고 종가 업데이트
            if data.close > position.highest_close:
                position.update_highest_close(data.close)
                # DB 업데이트
                if self.save_to_db and self.trade_repo:
                    self.trade_repo.update_highest_close(ticker, data.close)

            # 청산 시그널 확인
            exit_reason = self.strategy.check_exit_signal(
                ticker=ticker,
                data=data,
                entry_price=position.entry_price,
                entry_date=position.entry_date,
                highest_close=position.highest_close,
                initial_stop=position.initial_stop,
            )

            if exit_reason:
                positions_to_close.append((position.ticker, data.close, exit_reason, position))

        # 청산 처리
        for ticker, price, reason, position in positions_to_close:
            trade = self.portfolio.close_position(ticker, date, price, reason)
            
            if trade:
                # DB에 매도 기록 저장
                if self.save_to_db and self.trade_repo:
                    self.trade_repo.record_sell(
                        ticker=ticker,
                        trade_date=date,
                        price=price,
                        shares=trade.shares,
                        exit_reason=reason,
                        pnl=trade.pnl,
                        pnl_pct=trade.pnl_pct,
                        r_multiple=trade.r_multiple,
                    )
                
                if verbose:
                    print(f"[{date}] 매도: {ticker} @ {price:,.0f} ({reason}) "
                          f"PnL: {trade.pnl:+,.0f} ({trade.pnl_pct:+.2f}%)")

            if reason == "STOP_LOSS":
                self.stopped_out_today.add(ticker)

            if trade:
                is_stop = reason == "STOP_LOSS"
                self.risk_manager.on_trade_exit(
                    is_stop_loss=is_stop,
                    r_multiple=trade.r_multiple,
                    current_equity=self.portfolio.equity,
                )

    def _scan_entry_signals(
        self,
        date: str,
        tickers: list[str],
        data_cache: dict,
        verbose: bool,
    ):
        """신규 진입 시그널 스캔 → 대기 큐에 추가"""
        for ticker in tickers:
            if self.portfolio.has_position(ticker):
                continue
            
            if any(p.ticker == ticker for p in self.pending_entries):
                continue
            
            if ticker in self.stopped_out_today:
                continue

            data = data_cache.get(ticker, {}).get(date)
            if not data or not data.atr20:
                continue

            if self.strategy.check_entry_signal(ticker, data):
                pending = PendingEntry(
                    ticker=ticker,
                    signal_date=date,
                    signal_close=data.close,
                    atr=data.atr20,
                )
                self.pending_entries.append(pending)
                
                if verbose:
                    print(f"[{date}] 시그널: {ticker} (익일 시가 진입 예정)")

    def _generate_result(
        self,
        start_date: str,
        end_date: str,
        verbose: bool,
    ) -> dict:
        """백테스트 결과 생성"""
        stats = self.portfolio.get_stats()

        # DB 세션 ID 추가
        session_id = None
        if self.save_to_db and self.trade_repo:
            session_id = self.trade_repo.session_id

        if verbose:
            print("\n" + "=" * 60)
            print("백테스트 결과")
            print("=" * 60)
            print(f"총 거래 수: {stats['total_trades']}")
            print(f"승리 거래: {stats['winning_trades']}")
            print(f"손실 거래: {stats['losing_trades']}")
            print(f"승률: {stats['win_rate']:.2f}%")
            print(f"총 손익: {stats['total_pnl']:+,.0f}원")
            print(f"총 수익률: {stats['total_return_pct']:+.2f}%")
            print(f"최종 자산: {self.portfolio.equity:,.0f}원")
            if session_id:
                print(f"\n세션 ID: {session_id}")
                print("  (DB에서 'backtest_trades' 테이블 조회 가능)")

        return {
            "session_id": session_id,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": self.portfolio.initial_capital,
            "final_equity": self.portfolio.equity,
            "stats": stats,
            "trades": self.portfolio.trades,
            "daily_records": self.portfolio.daily_records,
            "risk_state": self.risk_manager.get_state_summary(),
        }
