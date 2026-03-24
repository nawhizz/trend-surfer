# 수정주가 이벤트 감지 및 백필 대상 종목 출력 개선

## Context

`scripts/update_adjusted_prices.py`가 미완성 상태로, 액면분할 등 수정주가 이벤트 감지 시 대상 종목을 명확하게 출력하고 백필을 수행하는 로직을 개선해야 함.

**현재 문제:**
- `get_db_yesterday_closes()` 함수가 `pass`로 비어있음
- `print()` 사용 (logger 미사용)
- 종목명 미출력 (종목코드만 표시)
- 전일 종가 조회 시 공휴일 미대응 (dt-1일만 확인)
- 날짜 형식 불일치 (`daily_routine.py`는 YYYY-MM-DD, 내부는 YYYYMMDD 가정)
- 백필에 `krx_collector.backfill_period()` 사용 (비수정주가) → `hybrid_collector` 사용이 적절
- 영어 주석 과다, 의사결정 과정이 코드에 남아있음

## 변경 파일

- `scripts/update_adjusted_prices.py` — 전면 리팩토링

## 구현 계획

### 1. 구조 개선 (함수 분리)

```
normalize_date(date_str) → (YYYYMMDD, YYYY-MM-DD)
fetch_db_latest_closes(db_tickers, before_date) → {ticker: {close, date}}
detect_adjustments(today_candles, db_closes, ticker_name_map, threshold) → list[dict]
print_detection_summary(candidates)
backfill_and_recalculate(candidates, start, end)
detect_and_update(target_date_str, threshold, backfill_start_date)  # 메인 (기존 인터페이스 유지)
```

### 2. 핵심 변경 사항

| 항목 | 기존 | 변경 |
|------|------|------|
| 전일 종가 조회 | dt-1일 고정 (공휴일 미대응) | 최대 7일 전까지 탐색 |
| 종목 정보 | 종목코드만 | 종목코드 + 종목명 |
| 출력 방식 | `print()` | `logger` (get_logger) |
| 결과 출력 | 단순 1줄 | 테이블 형식 요약 (종목코드, 종목명, DB종가, 추정전일, 차이율) |
| 백필 도구 | `krx_collector.backfill_period()` | `hybrid_collector.backfill_hybrid()` (FDR 수정주가) |
| 미사용 함수 | `get_db_yesterday_closes` (pass) | 삭제 |
| 주석 | 영어, 의사결정 과정 포함 | 한국어, 간결하게 정리 |
| 날짜 처리 | YYYYMMDD 고정 | YYYY-MM-DD / YYYYMMDD 자동 정규화 |

### 3. 감지 결과 출력 형식

```
======================================================================
수정주가 이벤트 감지: 2건
----------------------------------------------------------------------
종목코드  종목명          DB종가      추정전일      차이
----------------------------------------------------------------------
005930   삼성전자        70,000      35,000     50.0%
000660   SK하이닉스     180,000      90,000     50.0%
======================================================================
```

### 4. 메인 흐름

```
1. 날짜 정규화 (YYYY-MM-DD ↔ YYYYMMDD)
2. KRX API로 당일 시세 조회
3. DB 종목 마스터 조회 (ticker + name)
4. DB 전일 종가 조회 (최대 7일 전까지 탐색)
5. implied_prev = today_close / (1 + rate/100) vs DB 종가 비교
6. threshold(20%) 초과 종목 → 후보 리스트
7. 감지 결과 테이블 출력
8. hybrid_collector로 백필 + 지표 재계산
9. 완료 요약 출력
```

### 5. CLI 인터페이스 (변경 없음)

```bash
uv run ../scripts/update_adjusted_prices.py --date 2026-03-21 --threshold 0.20 --start_date 2020-01-01
```

`daily_routine.py`의 호출 방식과 완전 호환 유지.

## 검증 방법

1. `cd backend && uv run ../scripts/update_adjusted_prices.py --date 2026-03-21` 실행
2. 정상 종료 확인 (이벤트 없으면 "수정주가 이벤트 감지 없음" 출력)
3. 로거 출력 형식 확인
