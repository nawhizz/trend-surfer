# TrendSurfer 일일 루틴 전체 흐름

Windows 작업 스케줄러가 실행하는 `run_daily_routine.bat`에서 시작하여, 데이터 적재 → 종목 추출 → 텔레그램 전송까지의 모든 단계를 정리한 문서입니다.

---

## 0단계: 진입점 — `run_daily_routine.bat`

Windows 작업 스케줄러가 이 배치 파일을 실행합니다. (`scripts/run_daily_routine.bat`)

1. `backend/` 디렉토리로 이동 (`cd /d D:\...\backend`)
2. UTF-8 인코딩 강제 설정 (`chcp 65001`, `PYTHONIOENCODING=utf-8`) — 한글 로그 깨짐 방지
3. 로그 파일 경로 지정: `logs/daily_routine_YYYYMMDD.log`
4. `uv run ..\scripts\daily_routine.py` 실행, **모든 출력을 로그 파일로 리다이렉트** (`> %LOG_FILE% 2>&1`)

> ⚠️ **참고:** `daily_routine.py`를 인자 없이 실행하므로, 기준일은 **"전일"**이 됩니다. (KRX 공식 API가 당일 시세를 익일 오전에 공시하므로, 스케줄러를 익일 08:30에 실행하는 것을 전제로 함)

---

## 메인 오케스트레이터 — `daily_routine.py`

각 단계를 **subprocess**로 순차 실행합니다 (`scripts/daily_routine.py` 의 `run_script`).

핵심 메커니즘:
- 환경변수 `TREND_SURFER_SUBPROCESS=1`을 설정해, 하위 스크립트들은 **파일 로그를 직접 쓰지 않고 stdout만** 출력 → `daily_routine`이 stdout을 받아 **로그 파일에 단독 기록**하여 순서를 보장
- 단계가 **실패(exit≠0)하면 루틴 중단** (단, 5단계 경고종목은 실패해도 계속 진행)

---

## 단계 1: 종목 마스터 갱신

**명령:** `run_collector.py --mode tickers` → `collector.update_stock_list()`

- **FinanceDataReader**(`fdr.StockListing('KRX')`)로 전 종목 목록 조회 (KOSPI/KOSDAQ)
- `KRX-DESC`에서 섹터/산업 정보 보강
- 종목별로 가공:
  - **우선주/신주인수권 판정** (`is_preferred`): 6자리 숫자가 아니거나 끝자리가 0이 아니면 `True`
  - **활성 여부** (`is_active`): 종가가 0/NaN이면 비활성
- `stocks` 테이블에 **배치 upsert**
- **상장폐지 처리**: DB 활성 종목 중 FDR 목록에 없는 종목을 `is_active=False`로 비활성화

> ⚠️ FDR 기반이라 당일 데이터 404 영향을 받을 수 있으나, 예외를 삼켜 **exit 0**으로 루틴은 중단되지 않습니다.

---

## 단계 2: 수정주가 이벤트 감지 및 백필

**명령:** `update_adjusted_prices.py --date {기준일} --start_date 2020-01-01`

액면분할·무상증자 등으로 과거 데이터를 다시 받아야 하는 종목을 탐지합니다.

1. **KRX 공식 API**로 당일 전종목 시세 조회 (`krx_collector.fetch_market_ohlcv_by_date`)
   - **0건이면 휴장일/미공시로 판단하고 즉시 종료**
2. DB 종목 마스터로 필터링
3. DB에서 **전일 종가** 조회 (최대 7일 전까지 탐색, 연휴 대응)
4. **이벤트 감지 로직**: 등락률로 추정한 전일가(`today_close / (1+rate/100)`)와 DB 전일 종가를 비교 → 차이가 **임계값(20%)** 초과 시 수정주가 이벤트 후보로 판정
5. 후보가 있으면 **hybrid_collector**로 FDR 수정주가 기반 과거 데이터 백필 + **지표 재계산**

---

## 단계 3: 당일 시세 수집 (핵심 적재)

**명령:** `run_collector.py --mode daily --date {기준일}` → `collector.fetch_daily_ohlcv()`

1. **KRX 공식 인증 API**로 전종목 OHLCV 조회 (`krx_collector`)
   - **0건이면 WARNING 후 빈 리스트 반환**
2. **DB 등록 종목으로 필터링** — KRX가 반환하는 ETF/ETN/스팩 등은 `stocks`에 없어서 FK 제약 위반 방지
3. `daily_candles` 테이블에 **배치 upsert** (`on_conflict="ticker, date"` → 중복 시 갱신)

> 과거엔 FDR을 썼으나 GitHub 캐시 지연으로 당일 404가 빈번해 KRX 공식 API로 전환됨.

---

## 단계 4: 기술적 지표 계산

**명령:** `run_daily_indicators.py --date {기준일}` → `indicator_calculator.calculate_and_save_for_all_tickers(start=end=기준일)`

- 활성 종목 전체(약 2,737개)에 대해 **워커 8개로 병렬 계산**
- 계산 지표: MA(5/20/60/120/240), EMA(5/20/40/50/120/200/240), **EMA_STAGE**(대순환 1~6단계), ATR(20), HIGH(10/20)
- `daily_technical_indicators` 테이블에 저장

> ⚠️ 당일 캔들이 없으면 모든 종목이 "0건"으로 처리됨 (오류는 아니지만 실제 저장된 당일 지표 없음).

---

## 단계 5: 경고종목 업데이트 (실패 허용)

**명령:** `update_warning_stocks.py` → **키움증권 REST API (ka10099)**

1. **액세스 토큰 발급** (`client_credentials`)
   - `.env`의 `KIWOOM_IS_PAPER_TRADING` 값에 따라 호스트 결정 (`False`=실투자 `https://api.kiwoom.com`, `True`=모의 `https://mockapi.kiwoom.com`)
2. KOSPI(`mrkt_tp=0`), KOSDAQ(`10`) 종목 목록 조회 (연속조회 페이징)
3. `state`/`auditInfo` 키워드로 **warning_type 판정** (ADMIN/HALT/WARNING/CAUTION 등)
4. **양쪽 시장 모두 성공해야** `warning_type` 전체 초기화 후 재설정 (부분 데이터 리셋 방지)

> ⚠️ App Key/Secret 검증 실패 등으로 토큰 발급에 실패하면 이 단계는 스킵됩니다. 단, **이 단계는 실패해도 루틴 중단 안 됨**.

---

## 단계 6: 전략 신호 스캔 + 텔레그램 발송

**명령:** `run_strategy.py --date {기준일}` → `strategy_scanner.scan()`

1. **당일 일봉 조회** (`daily_candles`)
2. **유동성 필터**: 거래대금 ≥ 50억, 종가 ≥ 1,000원
3. **종목 정보 조회 & 제외**: 우선주, 시장경보(warning_type), 키워드(ETF/스팩 등), 비표준 코드
4. **지표 조회**: MA_20, HIGH_20, ATR_20, EMA_STAGE
5. **신호 분석** (추세추종 조건):
   - `종가 > MA(20)` (추세 상승)
   - `종가 > HIGH(20)` (20일 신고가 돌파)
   - `종가 > 시가` (양봉)
   - 만족 시 강도 = `(종가-시가)/시가 × 100`
6. **강도순 정렬** 후:
   - 콘솔/로그 출력
   - **엑셀 저장**: `results/signal_YYYYMMDD.xlsx`
   - **텔레그램 발송** (`notifier.send_signal_report`): 상위 20개 종목, 신호 없으면 "조건 충족 종목 없음" 메시지

> 📄 상세 문서
> - 스캔 조건(유동성/제외 필터, 진입 3조건, 백테스트 전략과의 차이): [전략 신호 스캔 조건 정리](./전략%20신호%20스캔%20조건%20정리.md)
> - 텔레그램 메시지 양식(API 스펙, 리포트/요약 포맷, 스테이지 이모지): [텔레그램 발송 양식 정의](./텔레그램%20발송%20양식%20정의.md)

---

## 전체 데이터 흐름 요약

```
run_daily_routine.bat (작업 스케줄러)
   └─ daily_routine.py (오케스트레이터, subprocess 순차 실행)
        ├─ 1. 종목 마스터  : FDR → stocks 테이블
        ├─ 2. 수정주가 감지 : KRX API ↔ DB 비교 → (이벤트시) 백필+지표재계산
        ├─ 3. 당일 시세    : KRX 공식 API → daily_candles 테이블  ★핵심 적재
        ├─ 4. 지표 계산    : daily_candles → daily_technical_indicators (병렬8)
        ├─ 5. 경고종목     : 키움 API → stocks.warning_type  (실패 허용)
        └─ 6. 전략 스캔    : candles+indicators → 필터/분석 → xlsx + 텔레그램 발송
```

**핵심 의존성:** 3단계(시세 적재)가 실패하면 4·6단계가 모두 빈 데이터로 동작합니다. 따라서 KRX 데이터가 공시되는 **익일 오전** 실행이 올바른 선택입니다.
