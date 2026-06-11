# TrendSurfer - Claude Code 프로젝트 가이드

## 프로젝트 개요

**TrendSurfer**는 한국 주식 시장(KOSPI, KOSDAQ)의 데이터를 수집·분석하고, 추세추종 전략 신호를 자동으로 포착·알림해주는 퀀트 투자 시스템입니다.

- **목적:** 직장인이 장중에 대응하기 어려운 문제를 해결하기 위해, 데이터 기반으로 매매 타이밍을 자동 식별
- **핵심 기능:** 일별 데이터 수집 → 기술적 지표 계산 → 전략 신호 스캔 → 알림 발송

---

## 언어 및 커뮤니케이션 규칙

- **응답 언어:** 한국어
- **코드 주석:** 한국어
- **커밋 메시지:** 한국어
- **문서:** 한국어
- **변수명/함수명:** 영어 (코드 표준 준수)

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **백엔드** | Python 3.13+, FastAPI, uv (패키지 매니저) |
| **프론트엔드** | Next.js (App Router), TypeScript, Tailwind CSS |
| **데이터베이스** | Supabase (PostgreSQL) |
| **데이터 수집** | pykrx, FinanceDataReader, KRX Open API |
| **지표 계산** | TA-Lib, pandas |
| **자동화** | Windows 작업 스케줄러 (scripts/run_daily_routine.bat) |

---

## 프로젝트 구조

```
trend-surfer-claude/
├── backend/                    # FastAPI 백엔드
│   ├── app/
│   │   ├── api/v1/             # API 엔드포인트
│   │   ├── backtest/           # 백테스트 엔진 및 전략
│   │   │   └── strategies/     # 개별 전략 구현체
│   │   ├── services/           # 비즈니스 로직 (수집, 계산)
│   │   ├── db/                 # DB 연결
│   │   ├── core/               # 설정 (config.py)
│   │   └── main.py             # FastAPI 진입점
│   ├── db/schema.sql           # DB 스키마 정의
│   └── .env                    # 환경 변수 (비공개)
├── scripts/                    # 실행 스크립트
│   ├── daily_routine.py        # [Daily] 일일 배치 메인 (자동화 진입점)
│   ├── run_strategy.py         # [Daily] 전략 신호 스캔
│   ├── run_backtest.py         # [Backtest] 백테스트 실행
│   ├── run_collector.py        # 데이터 수집 실행
│   ├── run_daily_indicators.py # 지표 계산 실행
│   ├── update_adjusted_prices.py # 수정주가 이벤트 감지 및 백필
│   ├── backfill_candles.py     # 과거 캔들 데이터 백필
│   ├── backfill_indicators.py  # 과거 지표 데이터 재계산
│   └── update_warning_stocks.py # 경고종목 업데이트 (키움 REST API)
├── frontend/                   # Next.js 프론트엔드
├── logs/                       # 일일 실행 로그
├── results/                    # 전략 신호 결과 (xlsx)
└── doc/                        # 프로젝트 문서 (PRD, TRD 등)
```

---

## 주요 명령어

> 모든 Python 스크립트는 `backend/` 디렉토리에서 `uv run`으로 실행합니다.

### 환경 설정

```bash
cd backend
uv sync
```

### 일일 자동화 루틴 (핵심)

```bash
cd backend
uv run ../scripts/daily_routine.py
```

내부 단계별 실행:
```bash
# 1. 종목 마스터 갱신
uv run ../scripts/run_collector.py --mode tickers

# 2. 수정주가 업데이트
uv run ../scripts/update_adjusted_prices.py

# 3. 당일 시세 수집 (OHLCV)
uv run ../scripts/run_collector.py --mode daily

# 4. 기술적 지표 계산
uv run ../scripts/run_daily_indicators.py

# 5. 경고종목 업데이트 (키움 API)
uv run ../scripts/update_warning_stocks.py

# 6. 전략 신호 스캔
uv run ../scripts/run_strategy.py
```

### 백테스트

```bash
cd backend

# 추세추종 전략 (기본 추천)
uv run ../scripts/run_backtest.py --start 2025-01-01 --strategy trend

# 지원 전략: trend | sma | ema | rsi
```

### 과거 데이터 백필

```bash
cd backend
uv run ../scripts/backfill_candles.py --start 2024-01-01 --end 2024-12-31
uv run ../scripts/backfill_indicators.py --start 2024-01-01 --end 2024-12-31
uv run ../scripts/backfill_index.py --start 2024-01-01
```

### API 서버 실행

```bash
cd backend
uv run uvicorn app.main:app --reload
```

---

## 환경 변수 (`backend/.env`)

```ini
SUPABASE_URL="YOUR_SUPABASE_URL"
SUPABASE_KEY="YOUR_SUPABASE_KEY"
KRX_API_KEY="YOUR_KRX_API_KEY"

# 키움증권 REST API (경고종목 조회용)
KIWOOM_APP_KEY="YOUR_KIWOOM_APP_KEY"
KIWOOM_APP_SECRET="YOUR_KIWOOM_APP_SECRET"
KIWOOM_IS_PAPER_TRADING=True
```

---

## 데이터 모델 (핵심 테이블)

### `stocks` - 종목 마스터
- `ticker` (PK): 종목 코드 (예: 005930)
- `name`: 종목명
- `market`: KOSPI / KOSDAQ
- `is_preferred`, `is_active`, `is_warning`: 우선주/활성/경고 여부

### `daily_candles` - 일봉 데이터
- `ticker`, `date`, `open`, `high`, `low`, `close`, `volume`, `amount`

### `daily_technical_indicators` - 기술적 지표
- MA(5/20/60/120/240), EMA(5/20/40/50/120/200/240)
- EMA_STAGE (이동평균 대순환 1~6단계)
- ATR(20일), HIGH(10/20일 최고가)

---

## 지원 전략

| ID | 전략명 | 설명 |
|----|--------|------|
| `trend` | TrendFollowing | **(추천)** 20일 신고가 + 50EMA 추세 + ATR 변동성 필터 |
| `sma` | SmaBreakout | 이동평균선(20/60/120) 정배열 + 신고가 돌파 |
| `ema` | EmaBreakout | 지수이동평균(20/50/120) 정배열 + 신고가 돌파 |
| `rsi` | RsiSwing | RSI 눌림목 매수 + 과매수 청산 |

---

## 개발 규칙

1. **우선주/ETF/ETN 및 관리종목 제외**: 전략 스캔 시 `is_preferred`, `is_warning` 필터 적용
2. **수정주가 기준**: 모든 분석은 수정주가(adjusted price) 기준으로 수행
3. **스크립트 경로**: `scripts/`는 `backend/` 상위에 위치하므로 `uv run ../scripts/xxx.py` 형식 사용
4. **로그**: `logs/` 디렉토리에 날짜별 저장 (`trend_surfer_YYYYMMDD.log`)
5. **결과**: `results/` 디렉토리에 날짜별 xlsx 저장 (`signal_YYYYMMDD.xlsx`)
6. **서브프로세스 로깅**: `daily_routine.py`가 스크립트를 subprocess로 실행할 때 `TREND_SURFER_SUBPROCESS=1` 환경변수를 설정함. `get_logger()`는 이 변수가 있으면 FileHandler를 추가하지 않고 stdout만 사용 — daily_routine이 로그 파일에 단독으로 기록해 순서를 보장함
7. **당일 시세 수집 (KRX 공식 API)**: `collector.fetch_daily_ohlcv()`와 `update_adjusted_prices.py`는 KRX 공식 인증 API(`krx_collector`, `KRX_API_KEY`)로 당일 전종목 시세를 조회한다. 0건이면 휴장일 또는 데이터 미공시로 판단하고 종료한다. (과거 FDR 폴백은 외부 GitHub 캐시 지연으로 당일 데이터에서 HTTP 404가 빈번해 제거함. pykrx는 **전종목 일괄 조회**(`get_market_ohlcv(date, market='ALL')`, `get_market_ticker_list`)가 KRX 차단으로 빈 응답을 반환해 사용 불가 — 2026-06 실측 시 `400 LOGOUT`이 아니라 빈 DataFrame→`KeyError: 시가/고가/저가/종가 컬럼 없음`, 종목리스트 0건으로 나타남. 단, **단일 종목 조회**(`get_market_ohlcv_by_date(start, end, ticker)`)는 정상 동작하나 원주가(비수정)이고 종목별 개별 호출이라 전종목 수집엔 부적합. 따라서 당일 전종목 시세는 KRX 공식 인증 API를 유지함.) KRX API는 ETF/ETN/스팩 등 `stocks` 마스터에 없는 종목도 반환하므로, `daily_candles` 저장 전 DB 등록 종목으로 필터링해 FK 제약 위반을 방지한다.
   - **단계 1(종목 마스터 `update_stock_list`)은 아직 FDR(`fdr.StockListing('KRX')`)을 사용**하며 동일한 404 영향을 받지만, 예외를 삼켜 exit 0이라 루틴은 중단되지 않는다(마스터 미갱신 상태로 진행). 필요 시 KRX 전환 검토.
8. **경고종목 업데이트**: KOSPI/KOSDAQ 중 하나라도 API 오류 시 DB 리셋을 하지 않음 (부분 데이터로 초기화 방지)
