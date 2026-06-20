# 추세추종 "2일 연속 EMA 이탈" 청산 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `TrendFollowingStrategy.check_exit_signal`의 미구현 TODO("2일 연속 EMA 이탈" 보조 청산)를 완성하여, 추세 둔화 국면에서 트레일링 스탑보다 빠르게 청산해 수익 반납을 줄인다.

**Architecture:** `Position`에 `ema_below_days` 카운터를 추가하고, 엔진의 `_process_exits`가 매일 청산 판정 직전에 이를 갱신(종가<50EMA면 +1, 아니면 0)한다. `check_exit_signal`은 이 카운터를 받아 `>= 2`이면 `EMA_STRUCTURE_EXIT`를 반환한다. 카운터 파라미터는 기본값을 가지므로 다른 전략은 동작 불변.

**Tech Stack:** Python 3.13+, dataclasses, pytest, uv

## Global Constraints

- 실행/테스트는 `backend/` 디렉토리에서 `uv run`으로 수행
- 콘솔 인코딩: `PYTHONUTF8=1`(또는 `PYTHONIOENCODING=utf-8`) 설정 필요 (이모지 출력 cp949 오류 회피)
- `check_exit_signal`은 `BaseStrategy`의 추상 메서드 — 시그니처 변경 시 base 및 4개 구현체(trend_following, sma_breakout, ema_breakout, rsi_swing) 모두 동일하게 맞춰야 함
- 새 파라미터 `ema_below_days: int = 0`은 **기본값 필수** (하위 호환)
- 상수 `EMA_BELOW_DAYS_THRESHOLD = 2`는 `trend_following.py`에 이미 정의돼 있음 — 신규 정의 금지, 그대로 사용
- 청산 사유 코드는 기존과 동일하게 `"EMA_STRUCTURE_EXIT"` 사용 (신규 사유 코드 만들지 않음)
- 작업 브랜치: `fix/ema-2day-exit` (이미 생성됨)

---

## File Structure

- **Modify** `backend/app/backtest/strategies/base.py` — `check_exit_signal` 추상 시그니처에 `ema_below_days: int = 0` 추가 + docstring
- **Modify** `backend/app/backtest/strategies/trend_following.py` — `check_exit_signal`에 파라미터 추가 + 2일 연속 이탈 청산 로직 구현 (TODO 제거)
- **Modify** `backend/app/backtest/strategies/sma_breakout.py` — 시그니처에 파라미터 추가 (동작 불변)
- **Modify** `backend/app/backtest/strategies/ema_breakout.py` — 시그니처에 파라미터 추가 (동작 불변)
- **Modify** `backend/app/backtest/strategies/rsi_swing.py` — 시그니처에 파라미터 추가 (동작 불변)
- **Modify** `backend/app/backtest/portfolio.py` — `Position`에 `ema_below_days: int = 0` 필드 추가
- **Modify** `backend/app/backtest/engine.py` — `_process_exits`에서 카운터 갱신 + `check_exit_signal` 호출 시 인자 전달
- **Create** `backend/tests/test_trend_following_exit.py` — `check_exit_signal` 보조 청산 단위 테스트

---

## Task 1: Position에 카운터 필드 추가

**Files:**
- Modify: `backend/app/backtest/portfolio.py` (Position dataclass, 약 27-34행)

**Interfaces:**
- Produces: `Position.ema_below_days: int` (기본값 0) — 엔진이 읽고 쓰며, 청산 판정에 전달

- [ ] **Step 1: `Position`에 필드 추가**

`portfolio.py`의 `Position` dataclass에서 `risk_amount: float = 0.0` 아래에 필드를 추가한다. (기본값 있는 필드 뒤에 기본값 있는 필드라 dataclass 순서 규칙 위반 없음)

```python
    atr_at_entry: float
    risk_amount: float = 0.0
    ema_below_days: int = 0   # 종가 < 50EMA 연속 일수 (보조 청산 판정용)
```

docstring의 Attributes 목록에도 한 줄 추가:

```python
        risk_amount: 이 포지션의 리스크 금액 (원)
        ema_below_days: 종가 < 50EMA 연속 일수 (보조 청산 판정용)
```

- [ ] **Step 2: import 정상 확인**

Run: `cd backend && uv run python -c "from app.backtest.portfolio import Position; p = Position(ticker='X', entry_date='2020-01-01', entry_price=100, shares=1, initial_stop=90, highest_close=100, atr_at_entry=5); print(p.ema_below_days)"`
Expected: `0` 출력 (에러 없음)

- [ ] **Step 3: Commit**

```bash
git add backend/app/backtest/portfolio.py
git commit -m "feat: Position에 ema_below_days 카운터 필드 추가"
```

---

## Task 2: check_exit_signal 시그니처에 ema_below_days 추가 (base + 전 전략)

**Files:**
- Modify: `backend/app/backtest/strategies/base.py:96-104`
- Modify: `backend/app/backtest/strategies/sma_breakout.py:72` 부근
- Modify: `backend/app/backtest/strategies/ema_breakout.py:72` 부근
- Modify: `backend/app/backtest/strategies/rsi_swing.py:70` 부근
- Modify: `backend/app/backtest/strategies/trend_following.py:127` 부근 (시그니처만; 로직은 Task 4)

**Interfaces:**
- Produces: 모든 전략의 `check_exit_signal(self, ticker, data, entry_price, entry_date, highest_close, initial_stop, ema_below_days=0) -> Optional[str]`

> **주의:** 이 태스크는 **시그니처에 파라미터만 추가**한다. trend_following의 청산 로직 변경은 Task 4에서 한다. sma/ema/rsi는 파라미터를 받기만 하고 사용하지 않는다(동작 불변).

- [ ] **Step 1: base.py 추상 시그니처 수정**

`base.py`의 `check_exit_signal`에 파라미터를 추가하고 docstring에 한 줄 보강:

```python
    def check_exit_signal(
        self,
        ticker: str,
        data: SignalData,
        entry_price: float,
        entry_date: str,
        highest_close: float,
        initial_stop: float,
        ema_below_days: int = 0,
    ) -> Optional[str]:
```

docstring Args에 추가:

```python
            initial_stop: 초기 손절가
            ema_below_days: 종가 < 50EMA 연속 일수 (보조 청산 판정용, 기본 0)
```

- [ ] **Step 2: sma_breakout / ema_breakout / rsi_swing 시그니처 수정**

세 파일의 `check_exit_signal` 정의에서 `initial_stop: float,` 다음 줄에 `ema_below_days: int = 0,`을 추가한다. 본문은 변경하지 않는다. 예 (sma_breakout.py):

```python
    def check_exit_signal(
        self,
        ticker: str,
        data: SignalData,
        entry_price: float,
        entry_date: str,
        highest_close: float,
        initial_stop: float,
        ema_below_days: int = 0,
    ) -> Optional[str]:
```

(ema_breakout.py, rsi_swing.py도 동일하게 `ema_below_days: int = 0,` 한 줄 추가)

- [ ] **Step 3: trend_following 시그니처만 수정**

`trend_following.py`의 `check_exit_signal` 정의에서도 `initial_stop: float,` 다음 줄에 `ema_below_days: int = 0,`을 추가한다. (본문 로직은 아직 변경하지 않음 — Task 4)

- [ ] **Step 4: 전 전략 import/인스턴스화 확인**

Run:
```bash
cd backend && uv run python -c "from app.backtest.strategies.trend_following import TrendFollowingStrategy; from app.backtest.strategies.sma_breakout import SmaBreakoutStrategy; from app.backtest.strategies.ema_breakout import EmaBreakoutStrategy; from app.backtest.strategies.rsi_swing import RsiSwingStrategy; [s() for s in [TrendFollowingStrategy, SmaBreakoutStrategy, EmaBreakoutStrategy, RsiSwingStrategy]]; print('ok')"
```
Expected: `ok` (추상 메서드 미구현 등 에러 없이 인스턴스화 성공)

- [ ] **Step 5: Commit**

```bash
git add backend/app/backtest/strategies/base.py backend/app/backtest/strategies/sma_breakout.py backend/app/backtest/strategies/ema_breakout.py backend/app/backtest/strategies/rsi_swing.py backend/app/backtest/strategies/trend_following.py
git commit -m "feat: check_exit_signal에 ema_below_days 파라미터 추가 (시그니처)"
```

---

## Task 3: 보조 청산 로직 테스트 작성 (실패 확인)

**Files:**
- Create: `backend/tests/test_trend_following_exit.py`

**Interfaces:**
- Consumes: `TrendFollowingStrategy.check_exit_signal(...)`, `SignalData`

> `check_exit_signal`은 DB에 의존하지 않는 순수 함수다. `SignalData`를 직접 구성해 테스트한다. 진입가/손절/최고종가는 손절·트레일링이 발동하지 않는 값으로 고정해, **보조 청산만** 검증한다.

- [ ] **Step 1: 테스트 파일 작성**

```python
"""
TrendFollowingStrategy.check_exit_signal 보조 청산(EMA 구조) 단위 테스트

DB 비의존 순수 함수. 손절/트레일링이 발동하지 않는 값으로 고정하여
EMA 보조 청산(기울기 급락 / 2일 연속 이탈)만 검증한다.
"""

import pytest

from app.backtest.strategies.trend_following import TrendFollowingStrategy
from app.backtest.strategies.base import SignalData


@pytest.fixture
def strategy():
    return TrendFollowingStrategy()


def make_data(close, ema50, ema50_slope, atr20=5.0):
    """손절/트레일링 미발동 조건의 SignalData 생성 헬퍼"""
    return SignalData(
        date="2025-01-10",
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000,
        ema50=ema50,
        ema50_slope=ema50_slope,
        atr20=atr20,
    )


# 공통 진입 컨텍스트: 손절/트레일링이 절대 발동하지 않도록 넉넉히 설정
ENTRY_PRICE = 100.0
INITIAL_STOP = 1.0       # 종가가 이보다 훨씬 위라 STOP_LOSS 미발동
HIGHEST_CLOSE = 100.0    # 트레일링: highest - 2.5*atr = 100 - 12.5 = 87.5 미만일 때만 발동


def test_no_exit_when_above_ema(strategy):
    """종가 > 50EMA 이고 다른 청산 조건 없으면 None"""
    data = make_data(close=99.0, ema50=95.0, ema50_slope=0.1)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=0,
    )
    assert result is None


def test_immediate_exit_on_steep_slope(strategy):
    """종가<50EMA AND 기울기<-0.3 → 즉시 EMA_STRUCTURE_EXIT (ema_below_days 무관)"""
    data = make_data(close=94.0, ema50=95.0, ema50_slope=-0.5)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=1,
    )
    assert result == "EMA_STRUCTURE_EXIT"


def test_no_exit_below_ema_first_day(strategy):
    """종가<50EMA 이지만 기울기 완만(-0.1)하고 1일째 이탈이면 청산 안 함"""
    data = make_data(close=94.0, ema50=95.0, ema50_slope=-0.1)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=1,
    )
    assert result is None


def test_exit_on_two_day_below_ema(strategy):
    """종가<50EMA 이고 기울기 완만(-0.1)해도 2일 연속 이탈이면 EMA_STRUCTURE_EXIT"""
    data = make_data(close=94.0, ema50=95.0, ema50_slope=-0.1)
    result = strategy.check_exit_signal(
        ticker="X", data=data, entry_price=ENTRY_PRICE, entry_date="2025-01-01",
        highest_close=HIGHEST_CLOSE, initial_stop=INITIAL_STOP, ema_below_days=2,
    )
    assert result == "EMA_STRUCTURE_EXIT"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && PYTHONUTF8=1 uv run pytest tests/test_trend_following_exit.py -v`
Expected: `test_exit_on_two_day_below_ema` FAIL (2일 연속 로직 미구현이라 None 반환). 나머지 3개는 PASS 가능. 최소 1개 FAIL이면 정상.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_trend_following_exit.py
git commit -m "test: 추세추종 보조 청산(2일 연속 EMA 이탈) 테스트 추가"
```

---

## Task 4: 2일 연속 이탈 청산 로직 구현 (TODO 제거)

**Files:**
- Modify: `backend/app/backtest/strategies/trend_following.py` (`check_exit_signal` 본문, 약 154-162행)

**Interfaces:**
- Consumes: `ema_below_days: int` 파라미터 (Task 2에서 추가), `self.EMA_BELOW_DAYS_THRESHOLD` (=2, 기존 상수)

- [ ] **Step 1: 보조 청산 블록 교체**

`trend_following.py`의 `check_exit_signal`에서 기존 보조 청산 블록(아래)을:

```python
        # 조건 3: 보조 청산 (50EMA 구조 붕괴)
        if data.ema50 and data.close < data.ema50:
            # 기울기가 급락하면 즉시 청산
            if data.ema50_slope and data.ema50_slope < self.EMA_SLOPE_EXIT_THRESHOLD:
                return "EMA_STRUCTURE_EXIT"
            
            # TODO: 2일 연속 이탈 확인은 추후 구현
            # 현재는 기울기 조건만 사용
        
        return None
```

다음으로 교체한다:

```python
        # 조건 3: 보조 청산 (50EMA 구조 붕괴)
        if data.ema50 and data.close < data.ema50:
            # 기울기가 급락하면 즉시 청산
            if data.ema50_slope and data.ema50_slope < self.EMA_SLOPE_EXIT_THRESHOLD:
                return "EMA_STRUCTURE_EXIT"
            
            # 2일 연속 50EMA 이탈이면 청산 (기울기가 완만해도 구조 둔화로 판단)
            if ema_below_days >= self.EMA_BELOW_DAYS_THRESHOLD:
                return "EMA_STRUCTURE_EXIT"
        
        return None
```

- [ ] **Step 2: 테스트 실행 → 전체 통과 확인**

Run: `cd backend && PYTHONUTF8=1 uv run pytest tests/test_trend_following_exit.py -v`
Expected: 4개 테스트 모두 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/backtest/strategies/trend_following.py
git commit -m "feat: 추세추종 2일 연속 EMA 이탈 보조 청산 구현 (TODO 제거)"
```

---

## Task 5: 엔진에서 카운터 갱신 + 인자 전달

**Files:**
- Modify: `backend/app/backtest/engine.py` (`_process_exits`, 약 460-482행)

**Interfaces:**
- Consumes: `Position.ema_below_days` (Task 1), `check_exit_signal(..., ema_below_days=...)` (Task 2/4)

- [ ] **Step 1: 카운터 갱신 + 인자 전달 추가**

`_process_exits` 안에서, "최고 종가 업데이트" 블록과 "청산 시그널 확인" 사이에 카운터 갱신을 삽입하고, `check_exit_signal` 호출에 인자를 추가한다.

기존:

```python
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
```

교체:

```python
            # 최고 종가 업데이트
            if data.close > position.highest_close:
                position.update_highest_close(data.close)
                # DB 업데이트
                if self.save_to_db and self.trade_repo:
                    self.trade_repo.update_highest_close(ticker, data.close)

            # EMA 이탈 연속 일수 갱신 (청산 판정 직전에 수행해야 당일 이탈이 반영됨)
            # ema50 결측이면 카운터 변경하지 않음(보수적)
            if data.ema50:
                if data.close < data.ema50:
                    position.ema_below_days += 1
                else:
                    position.ema_below_days = 0

            # 청산 시그널 확인
            exit_reason = self.strategy.check_exit_signal(
                ticker=ticker,
                data=data,
                entry_price=position.entry_price,
                entry_date=position.entry_date,
                highest_close=position.highest_close,
                initial_stop=position.initial_stop,
                ema_below_days=position.ema_below_days,
            )
```

- [ ] **Step 2: 엔진 import 및 단일 종목 스모크 테스트**

Run: `cd backend && PYTHONUTF8=1 uv run ../scripts/run_backtest.py --start 2025-01-01 --ticker 005930 --strategy trend --quiet`
Expected: 에러 없이 "백테스트 상세 결과" 요약이 출력됨 (수치는 변경 전과 달라질 수 있음 — 정상)

- [ ] **Step 3: 전체 테스트 스위트 회귀 확인**

Run: `cd backend && PYTHONUTF8=1 uv run pytest -q`
Expected: 기존 테스트 + 신규 테스트 전부 PASS (시그니처 변경이 기존 전략 동작을 깨지 않음 확인)

- [ ] **Step 4: Commit**

```bash
git add backend/app/backtest/engine.py
git commit -m "feat: 엔진이 ema_below_days 매일 갱신 후 청산 판정에 전달"
```

---

## Task 6: 검증 백테스트 (2020~2026 전체) + 결과 기록

**Files:**
- (코드 변경 없음) 결과만 비교

**Interfaces:**
- Consumes: 완성된 전략·엔진

- [ ] **Step 1: 전체 종목 재백테스트 실행**

Run (백그라운드 권장):
```bash
cd backend && PYTHONUTF8=1 uv run ../scripts/run_backtest.py --start 2020-01-01 --end 2026-06-20 --strategy trend --output ../results --quiet
```
Expected: 정상 완료(exit 0), "백테스트 상세 결과" 요약 출력

- [ ] **Step 2: 변경 전후 비교**

변경 전 기준선(2026-06-20 측정): 총수익률 +54.34% / CAGR 6.94% / 거래 97 / 승률 32.0% / 손익비 1.80 / MDD 19.40% / 평균보유 50.4일 / 최대연패 17.

변경 후 수치를 같은 항목으로 표 정리한다. **기대:** EMA_STRUCTURE_EXIT 청산 증가, 평균 보유기간 단축. **개선이 없거나 악화될 수도 있음** — 그 경우 사실대로 보고하고 롤백 여부를 사용자와 판단(과최적화 경계).

- [ ] **Step 3: 결과를 설계 문서 하단에 추가 기록 + 커밋**

`docs/superpowers/specs/2026-06-20-ema-2day-exit-design.md` 하단에 "## 7. 검증 결과" 절을 추가하고 비교 표를 기록한다.

```bash
git add docs/superpowers/specs/2026-06-20-ema-2day-exit-design.md
git commit -m "docs: 2일 연속 EMA 이탈 청산 검증 결과 기록"
```

---

## Self-Review

**1. Spec coverage:**
- 설계 4.1(1) Position 카운터 → Task 1 ✅
- 설계 4.1(2) 엔진 매일 갱신 → Task 5 ✅
- 설계 4.1(3) 전략 청산 판정 → Task 2(시그니처) + Task 4(로직) ✅
- 설계 4.2 갱신 규칙(+1/리셋) → Task 5 Step 1 ✅
- 설계 4.4 엣지(ema50 결측/동시 성립) → Task 5(결측 미변경) + Task 3 테스트(즉시청산 우선) ✅
- 설계 5 검증 계획 → Task 6 ✅
- 비목표(불타기/ATR/_P) → 어떤 태스크도 건드리지 않음 ✅

**2. Placeholder scan:** 모든 코드 스텝에 실제 코드/명령/기대출력 포함. TODO/TBD 없음(기존 코드의 TODO는 Task 4에서 제거). ✅

**3. Type consistency:** `ema_below_days: int = 0` 명칭·타입이 base/4전략/Position/engine 호출 전부 일치. 사유 코드 `"EMA_STRUCTURE_EXIT"` 통일. 상수 `EMA_BELOW_DAYS_THRESHOLD` 기존 정의 재사용. ✅
