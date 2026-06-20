# 설계: 추세추종 보조 청산 "2일 연속 EMA 이탈" 구현 (#1)

- **작성일:** 2026-06-20
- **대상:** `backend/app/backtest/strategies/trend_following.py`, `backend/app/backtest/engine.py`, `backend/app/backtest/portfolio.py`
- **분류:** 백테스트 전략 결함 수정 (#1 TODO 청산)

---

## 1. 배경 및 문제

`TrendFollowingStrategy.check_exit_signal`의 docstring은 보조 청산을 다음과 같이 정의한다.

> 종가 < 50EMA AND (기울기 < -0.3 OR **2일 연속 이탈**)

그러나 실제 코드에는 `# TODO: 2일 연속 이탈 확인은 추후 구현`만 남아 있고, **기울기 < -0.3 조건만 동작**한다(`trend_following.py:160`). 그 결과:

- 추세가 완만히 꺾이는 국면(가격이 50EMA 아래로 내려갔지만 기울기는 -0.3까지 빠지지 않은 상태)에서 보조 청산이 발동하지 않는다.
- 이런 포지션은 트레일링 스탑(`최고 종가 - 2.5 × ATR`)까지 끌려가며 **수익을 반납**한다.

2020-01-01 ~ 2026-06-20 백테스트 결과(CAGR 6.94%, 평균 보유 50.4일, 최대 17연패)에서 수익 반납이 의심되는 지점이다.

## 2. 목표

docstring이 약속한 보조 청산을 완성한다. 추세 둔화 국면에서 트레일링 스탑보다 빠르게 청산하여 수익 반납을 줄인다.

## 3. 비목표 (범위 밖)

- 불타기(피라미딩, #2) 및 불타기 `_P` 포지션 청산 누락 버그(버그 A) — 별도 작업
- ATR 과열 임계값 8% vs 15% 불일치(#3) — 별도 작업
- 청산 우선순위/사유 체계 재설계
- 신규 진입 조건 변경

## 4. 설계

### 4.1 변경 컴포넌트 (3곳)

#### (1) `Position`에 카운터 필드 추가 — `portfolio.py`

```python
ema_below_days: int = 0   # 종가 < 50EMA 연속 일수 (보조 청산 판정용)
```

- `@dataclass`의 기본값 0이므로 기존 호출부와 다른 전략에 영향 없음.

#### (2) 엔진이 매일 카운터 갱신 — `engine.py` `_process_exits`

청산 시그널 확인 **직전**(최고 종가 업데이트 이후), 각 포지션에 대해:

| 조건 | 동작 |
|------|------|
| `data.ema50`이 결측(None/0) | 카운터 변경 없음 (보수적) |
| `data.close < data.ema50` | `position.ema_below_days += 1` |
| `data.close >= data.ema50` | `position.ema_below_days = 0` (리셋) |

> **순서가 중요:** 카운터를 먼저 갱신한 뒤 `check_exit_signal`에 넘겨야 당일 이탈이 판정에 반영된다.

#### (3) 전략이 카운터로 청산 판정 — `trend_following.py` `check_exit_signal`

시그니처에 `ema_below_days: int = 0` 파라미터 추가(기본값으로 하위 호환). 기존 보조 청산 블록을 다음으로 교체:

```python
if data.ema50 and data.close < data.ema50:
    # 즉시 청산: 기울기 급락
    if data.ema50_slope and data.ema50_slope < self.EMA_SLOPE_EXIT_THRESHOLD:
        return "EMA_STRUCTURE_EXIT"
    # 2일 연속 이탈 청산 (신규)
    if ema_below_days >= self.EMA_BELOW_DAYS_THRESHOLD:   # = 2
        return "EMA_STRUCTURE_EXIT"
```

- 이미 정의돼 있으나 미사용이던 상수 `EMA_BELOW_DAYS_THRESHOLD = 2`를 사용.
- 두 보조 청산은 동일 사유 코드 `EMA_STRUCTURE_EXIT`로 통일.

### 4.2 카운터 갱신 규칙 (확정)

종가가 50EMA 아래면 +1, 50EMA 이상이면 0으로 **리셋**한다. 즉 "연속 2일"의 자연스러운 해석을 따른다. 일시 반등으로 이탈이 끊기면 카운터는 다시 0부터 센다. (누적 방식은 채택하지 않음 — "연속"의 의미와 불일치)

### 4.3 데이터 흐름

```
_process_exits (매일, 포지션별)
  ├─ 최고 종가 업데이트
  ├─ [신규] ema_below_days 갱신 (close < ema50 ? +1 : 0)
  └─ check_exit_signal(... ema_below_days) → 사유 반환 시 청산
```

### 4.4 엣지 케이스

| 상황 | 처리 |
|------|------|
| `ema50` 결측 | 카운터 미변경, 보조 청산 미발동 (안전) |
| 즉시 청산(기울기<-0.3)과 2일 청산 동시 성립 | 같은 사유라 무해. 먼저 평가되는 기울기 조건이 반환 |
| 불타기 `_P` 포지션 | 버그 A로 `data`가 None이라 이 경로 미진입 — 본 작업 범위 밖 |

## 5. 검증 계획

구현 후 **2020-01-01 ~ 2026-06-20, 전체 활성 보통주, 초기자본 1억, 추세추종** 동일 조건으로 재백테스트.

- **비교 지표:** 총수익률, CAGR, 승률, 손익비, 평균 R, MDD, 평균 보유기간, EMA_STRUCTURE_EXIT 청산 건수
- **기대:** EMA_STRUCTURE_EXIT 청산 증가, 평균 보유기간 단축, 수익 반납 감소
- **주의:** 개선이 없거나 악화될 수도 있음. 그 경우도 유효한 결과로 보고하고 롤백 여부를 판단한다(과최적화 경계).

## 6. 영향 범위

- 다른 전략(sma/ema/rsi)은 `check_exit_signal` 시그니처에 기본값 파라미터가 추가될 뿐 동작 불변.
- `Position` 필드 추가는 직렬화·DB 기록에 영향 없음(메모리 객체 한정).
