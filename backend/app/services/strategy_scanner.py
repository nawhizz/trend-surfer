"""
전략 신호 스캐너 서비스

추세추종 전략 조건에 맞는 종목을 스캔하고 신호를 생성합니다.
조건: 20일 이동평균 위 + 20일 신고가 돌파 + 양봉
"""

import json
from dataclasses import dataclass

from app.db.client import supabase
from app.core.logger import get_logger
from app.core.constants import (
    BATCH_READ_PAGE,
    BATCH_IN_FILTER,
    DEFAULT_MIN_AMOUNT,
    DEFAULT_MIN_PRICE,
    EXCLUDE_KEYWORDS,
)

logger = get_logger(__name__)


@dataclass
class ScanConfig:
    """스캐너 설정"""
    target_date: str
    min_amount: int = DEFAULT_MIN_AMOUNT
    min_price: int = DEFAULT_MIN_PRICE


class StrategyScanner:
    """추세추종 전략 신호 스캐너"""

    def scan(self, config: ScanConfig) -> list[dict]:
        """
        전략 신호 스캔 실행

        Args:
            config: 스캔 설정

        Returns:
            신호 리스트 (강도 내림차순 정렬)
        """
        # 1. 일봉 데이터 조회
        candles = self._fetch_candles(config.target_date)
        if not candles:
            return []

        # 2. 유동성 필터
        target_tickers, filtered_candle_map = self._apply_liquidity_filter(
            candles, config.min_amount, config.min_price
        )
        if not target_tickers:
            logger.warning("유동성 필터 통과 종목이 없습니다.")
            return []

        # 3. 종목 정보 조회 및 위험종목 제외
        ticker_name_map, ticker_excluded = self._fetch_stock_info(target_tickers)
        if ticker_excluded:
            original_count = len(target_tickers)
            target_tickers = [t for t in target_tickers if t not in ticker_excluded]
            filtered_candle_map = {
                k: v for k, v in filtered_candle_map.items() if k not in ticker_excluded
            }
            logger.info(
                f"제외 종목 {original_count - len(target_tickers)}개 "
                f"(우선주/ETF/ETN/스팩 등). 잔여: {len(target_tickers)}개"
            )

        if not target_tickers:
            return []

        # 4. 지표 조회
        ind_map = self._fetch_indicators(target_tickers, config.target_date)

        # 5. 신호 분석
        signals = self._analyze_signals(
            target_tickers, filtered_candle_map, ind_map, ticker_name_map
        )

        # 6. 강도순 정렬
        signals.sort(key=lambda x: x["strength"], reverse=True)
        logger.info(f"[신호 결과] {len(signals)}개 종목 발견")

        return signals

    # ========================================
    # 데이터 조회
    # ========================================

    def _fetch_candles(self, target_date: str) -> list[dict]:
        """당일 일봉 데이터 조회"""
        logger.info("일봉 데이터 조회 중...")
        try:
            candles = []
            offset = 0
            while True:
                resp = (
                    supabase.table("daily_candles")
                    .select("ticker, open, close, volume, amount")
                    .eq("date", target_date)
                    .range(offset, offset + BATCH_READ_PAGE - 1)
                    .execute()
                )
                if not resp.data:
                    break
                candles.extend(resp.data)
                offset += BATCH_READ_PAGE
                if len(resp.data) < BATCH_READ_PAGE:
                    break

            logger.info(f"일봉 {len(candles)}건 조회 완료")
            return candles
        except Exception as e:
            logger.error(f"일봉 데이터 조회 실패: {e}", exc_info=True)
            return []

    def _fetch_stock_info(
        self, tickers: list[str]
    ) -> tuple[dict[str, str], set[str]]:
        """
        종목 정보 조회 및 제외 대상 식별

        Returns:
            (ticker -> name 맵, 제외할 ticker 집합)
        """
        logger.info("종목명 조회 중...")
        ticker_name_map: dict[str, str] = {}
        ticker_excluded: set[str] = set()

        try:
            for i in range(0, len(tickers), BATCH_IN_FILTER):
                batch = tickers[i : i + BATCH_IN_FILTER]
                resp = (
                    supabase.table("stocks")
                    .select("ticker, name, is_preferred, warning_type")
                    .in_("ticker", batch)
                    .execute()
                )
                if not resp.data:
                    continue

                for item in resp.data:
                    ticker = item["ticker"]
                    name = item["name"] or ""
                    ticker_name_map[ticker] = name

                    if self._should_exclude(
                        ticker, name, item.get("is_preferred", False), item.get("warning_type")
                    ):
                        ticker_excluded.add(ticker)

        except Exception as e:
            logger.warning(f"종목명 조회 실패 (계속 진행): {e}")

        return ticker_name_map, ticker_excluded

    def _fetch_indicators(
        self, tickers: list[str], target_date: str
    ) -> dict[str, dict]:
        """
        대상 종목의 기술적 지표 조회

        Returns:
            {ticker: {MA_20, HIGH_20, ATR_20, EMA_STAGE}} 맵
        """
        logger.info("대상 종목 지표 조회 중...")
        indicators = []

        try:
            total_batches = (len(tickers) + BATCH_IN_FILTER - 1) // BATCH_IN_FILTER
            for i in range(0, len(tickers), BATCH_IN_FILTER):
                batch = tickers[i : i + BATCH_IN_FILTER]
                resp = (
                    supabase.table("daily_technical_indicators")
                    .select("ticker, indicator_type, params, value")
                    .eq("date", target_date)
                    .in_("ticker", batch)
                    .in_("indicator_type", ["MA", "HIGH", "ATR", "EMA_STAGE"])
                    .execute()
                )
                if resp.data:
                    indicators.extend(resp.data)
                logger.debug(f"배치 {i // BATCH_IN_FILTER + 1}/{total_batches} 조회 완료")

            logger.info(f"지표 {len(indicators)}건 조회 완료")
        except Exception as e:
            logger.error(f"지표 조회 실패: {e}", exc_info=True)
            return {}

        return self._build_indicator_map(indicators)

    # ========================================
    # 필터 및 분석 로직
    # ========================================

    @staticmethod
    def _apply_liquidity_filter(
        candles: list[dict], min_amount: int, min_price: int
    ) -> tuple[list[str], dict[str, dict]]:
        """유동성 필터 적용"""
        target_tickers = []
        filtered_map = {}

        for c in candles:
            amount = c.get("amount") or (c["close"] * c["volume"])
            if amount >= min_amount and c["close"] >= min_price:
                if c["ticker"] not in filtered_map:
                    target_tickers.append(c["ticker"])
                    filtered_map[c["ticker"]] = c

        logger.info(
            f"유동성 필터 후 {len(target_tickers)}개 "
            f"(거래대금 >= {min_amount:,}, 가격 >= {min_price:,})"
        )
        return target_tickers, filtered_map

    @staticmethod
    def _should_exclude(
        ticker: str, name: str, is_preferred: bool, warning_type: str | None
    ) -> bool:
        """종목 제외 조건 검사"""
        # 1. 우선주
        if is_preferred:
            return True
        # 2. 시장경보 종목
        if warning_type:
            return True
        # 3. 종목명 키워드
        for keyword in EXCLUDE_KEYWORDS:
            if keyword in name:
                return True
        # 4. 종목코드 패턴 (6자리 숫자가 아니면 제외)
        if not (ticker.isdigit() and len(ticker) == 6):
            return True
        return False

    @staticmethod
    def _build_indicator_map(indicators: list[dict]) -> dict[str, dict]:
        """지표 리스트를 {ticker: {key: value}} 맵으로 변환"""
        ind_map: dict[str, dict] = {}

        for ind in indicators:
            t = ind["ticker"]
            if t not in ind_map:
                ind_map[t] = {}

            itype = ind["indicator_type"]
            params = json.loads(ind["params"])
            val = ind["value"]

            if itype == "MA" and params.get("period") == 20:
                ind_map[t]["MA_20"] = val
            elif itype == "HIGH" and params.get("period") == 20:
                ind_map[t]["HIGH_20"] = val
            elif itype == "ATR" and params.get("period") == 20:
                ind_map[t]["ATR_20"] = val
            elif itype == "EMA_STAGE":
                ind_map[t]["EMA_STAGE"] = val

        return ind_map

    @staticmethod
    def _analyze_signals(
        tickers: list[str],
        candle_map: dict[str, dict],
        ind_map: dict[str, dict],
        name_map: dict[str, str],
    ) -> list[dict]:
        """추세추종 전략 신호 분석"""
        signals = []

        for ticker in tickers:
            c_data = candle_map[ticker]
            open_p = c_data["open"]
            close = c_data["close"]
            volume = c_data["volume"]
            amount = c_data.get("amount") or (close * volume)
            name = name_map.get(ticker, "Unknown")

            i_data = ind_map.get(ticker, {})
            ma_20 = i_data.get("MA_20")
            high_20 = i_data.get("HIGH_20")
            atr_20 = i_data.get("ATR_20")
            ema_stage = i_data.get("EMA_STAGE", 0)

            if ma_20 is None or high_20 is None:
                continue

            # 전략 조건: MA(20) 위 + 20일 신고가 돌파 + 양봉
            is_trend_up = close > ma_20
            is_breakout = close > high_20
            is_positive_candle = close > open_p

            if is_trend_up and is_breakout and is_positive_candle:
                strength = ((close - open_p) / open_p) * 100 if open_p > 0 else 0

                signals.append({
                    "ticker": ticker,
                    "name": name,
                    "close": close,
                    "strength": round(strength, 2),
                    "amount_b": round(amount / 100_000_000, 1),
                    "ma_20": ma_20,
                    "high_20": high_20,
                    "atr_20": atr_20 if atr_20 is not None else 0,
                    "stage": int(ema_stage) if ema_stage is not None else 0,
                })

        return signals


# 싱글톤 인스턴스
strategy_scanner = StrategyScanner()
