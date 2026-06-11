# TrendSurfer Backend

TrendSurfer의 백엔드 시스템입니다. 한국 주식 시장(KOSPI, KOSDAQ)의 데이터를 수집하고, 정량적 전략(Quantitative Strategy)을 실행 및 검증합니다.

## 🛠 기술 스택

- **Framework**: FastAPI
- **Language**: Python 3.13+
- **Manager**: [uv](https://github.com/astral-sh/uv)
- **Database**: Supabase (PostgreSQL)
- **Data**: KRX 공식 인증 API(당일 시세), FinanceDataReader(종목 마스터·수정주가 백필), 키움증권 REST API(경고종목)

> **데이터 소스 정책**
> - **종목 마스터**(`stocks`): FDR `fdr.StockListing('KRX' / 'KRX-DESC')`
> - **당일 시세**(`daily_candles`): **KRX 공식 인증 API**(`data-dbg.krx.co.kr`, `KRX_API_KEY`). 과거 FDR을 썼으나 외부 GitHub 캐시 지연으로 당일 데이터 HTTP 404가 빈번해 전환함.
> - **과거/수정주가 백필**: 하이브리드 — FDR(수정주가 OHLCV) + KRX 공식 API(거래대금·시가총액).
> - `pykrx`는 KRX 웹 차단(`400 LOGOUT`)으로 **사용하지 않음**.

---

## 🚀 시작하기 (Getting Started)

### 1. 환경 설정

`uv` 패키지 매니저가 설치되어 있어야 합니다.

```bash
# 프로젝트 의존성 설치
uv sync
```

### 2. 환경 변수 설정
`backend/.env` 파일을 생성하고 아래 내용을 설정하세요.

```ini
SUPABASE_URL="YOUR_SUPABASE_URL"
SUPABASE_KEY="YOUR_SUPABASE_KEY"
KRX_API_KEY="YOUR_KRX_API_KEY"

# 키움증권 REST API (경고종목 조회용)
KIWOOM_APP_KEY="YOUR_KIWOOM_APP_KEY"
KIWOOM_APP_SECRET="YOUR_KIWOOM_APP_SECRET"
KIWOOM_IS_PAPER_TRADING=True
```

### 3. 서버 실행 (API)
데이터 수집 및 백테스트는 스크립트로 실행하므로, API 서버 실행은 필수적인 것은 아닙니다.

```bash
uv run uvicorn app.main:app --reload
```

---

## 📅 Daily Operation (매일 작업)

매일 장 마감 후 실행하는 자동화 루틴입니다. 데이터 수집, 보정, 지표 계산, 시그널 생성을 일괄 처리합니다.

### 1. 자동 실행 (One-Step)
가장 권장되는 방법입니다. `daily_routine.py`가 아래 모든 단계를 순차적으로 실행합니다.

```bash
# 실행 (backend 디렉토리에서)
uv run ../scripts/daily_routine.py
```

**윈도우 작업 스케줄러 등록**:
`scripts/run_daily_routine.bat` 파일을 등록하여 매일 자동 실행되도록 설정할 수 있습니다.

> ⚠️ **실행 시각 주의 (중요)**: KRX 공식 API의 전종목 일별 시세는 장 마감(15:30) 후 정산을 거쳐 공시되므로, **16:30 실행 시 아직 데이터가 올라오지 않아 0건이 반환될 수 있습니다.** 이 경우 코드는 "휴장일 또는 데이터 미공시"로 간주하고 저장 없이 종료하여 `daily_candles`에 데이터가 적재되지 않습니다. **트리거 시각을 18:00 이후로 설정하는 것을 권장합니다.** 누락이 발생하면 익일 [과거 데이터 백필](#과거-데이터-백필-backfill)로 복구할 수 있습니다.

### 2. 상세 프로세스 (Internal Steps)
`daily_routine.py`는 내부적으로 다음 스텝을 수행합니다. 필요 시 개별 스크립트를 수동으로 실행할 수 있습니다.

| 단계 | 스크립트 | 설명 |
|------|----------|------|
| **1. 종목 갱신** | `run_collector.py --mode tickers` | 신규 상장/상장 폐지 종목 마스터 업데이트 (FDR). 우선주·신주인수권증서 등 비표준 종목은 `is_preferred`로 자동 분류 |
| **2. 수정주가** | `update_adjusted_prices.py` | 액면분할·무상증자 등 이벤트 감지 및 과거 데이터 자동 백필 (KRX 등락률 역산 vs DB 종가 비교) |
| **3. 시세 수집** | `run_collector.py --mode daily` | 당일 전종목 OHLCV·거래대금·시가총액 수집 (**KRX 공식 API**). `stocks` 미등록 종목은 FK 위반 방지를 위해 필터링 |
| **4. 지표 계산** | `run_daily_indicators.py` | 당일 캔들 기준 기술적 지표(MA, EMA_STAGE, ATR 등) 계산 |
| **5. 경고종목** | `update_warning_stocks.py` | 관리종목, 투자경고, 거래정지 등 경고 상태 업데이트 (키움 API). KOSPI/KOSDAQ 중 하나라도 오류 시 DB를 리셋하지 않아 부분 데이터 초기화 방지 |
| **6. 전략 실행** | `run_strategy.py` | 20일 신고가 추세추종 시그널 스캔 → 엑셀 저장 → **텔레그램 발송**. 우선주/ETF/ETN/경고종목 제외 |

> **단계별 실패 정책**: 단계 1·3·4·6은 실패 시 루틴이 중단되지만(`exit 1`), 단계 2(수정주가)는 데이터 미공시 시 정상 종료하고, 단계 5(경고종목)는 실패해도 경고하고 계속 진행합니다. 특정 날짜를 지정하려면 `--date YYYY-MM-DD`를 사용합니다.

---

## 🧪 Backtest & Strategy (백테스트 및 분석)

과거 데이터를 기반으로 전략의 성과를 검증합니다.

### 1. 백테스트 실행

```bash
cd backend

# 추세추종 전략 (추천)
uv run ../scripts/run_backtest.py --start 2025-01-01 --strategy trend

# SMA 돌파 전략
uv run ../scripts/run_backtest.py --start 2025-01-01 --strategy sma

# 결과 파일 저장
uv run ../scripts/run_backtest.py --start 2025-01-01 --strategy trend --output ./results
```

### 2. 지원 전략 목록

| ID | 전략명 | 설명 |
|----|--------|------|
| `trend` | **TrendFollowing** | **(추천)** 20일 신고가 + 50EMA 추세 + ATR 변동성 필터. 손익비 극대화 전략. |
| `sma` | SmaBreakout | 이동평균선(20/60/120) 정배열 + 신고가 돌파. |
| `ema` | EmaBreakout | 지수이동평균(20/50/120) 정배열 + 신고가 돌파. |
| `rsi` | RsiSwing | RSI 눌림목 매수 + 과매수 청산 (단기 스윙). |

---

## 📊 Technical Indicators (기술적 지표)

시스템에서 자동 계산 및 관리하는 주요 기술적 지표입니다.

| 지표명 | 설명 | 주요 파라미터/설명 |
|---|---|---|
| **MA** | 단순 이동평균 (SMA) | 5, 20, 60, 120, 240일 |
| **EMA** | 지수 이동평균 (EMA) | 5, 20, 40, 50, 120, 200, 240일 |
| **EMA_STAGE** | **이동평균 대순환 스테이지** | EMA(5, 20, 40) 배열에 따른 시장 국면 진단 (1~6단계) |
| **ATR** | 평균 변동성 (Usage) | 20일 (손절 및 포지션 사이징용) |
| **HIGH** | 기간 내 최고 종가 | 10일, 20일 (신고가 돌파 매매용) |

### 📈 EMA Stage (이동평균선 대순환 분석)
단기(5일), 중기(20일), 장기(40일) 지수이동평균의 배열 상태를 분석하여 현재 추세 국면을 6단계로 구분합니다.

| Stage | 명칭 | 상태 (배열) | 투자 전략 |
|:---:|:---:|---|---|
| **1** | **안정 상승기** | 단기 > 중기 > 장기 | **[매수]** 강력한 상승 추세 (보유/추가 매수) |
| **2** | 하락 변화기 1 | 중기 > 단기 > 장기 | **[이익 실현]** 상승세 둔화, 조정 가능성 |
| **3** | 하락 변화기 2 | 중기 > 장기 > 단기 | **[매도 준비]** 하락 전환 신호 |
| **4** | **안정 하락기** | 장기 > 중기 > 단기 | **[매도]** 확연한 하락 추세 |
| **5** | 상승 변화기 1 | 장기 > 단기 > 중기 | **[매도 청산]** 바닥 다지기, 반등 시도 |
| **6** | **상승 변화기 2** | 단기 > 장기 > 중기 | **[매수 급소]** 상승 추세 초입 (선취매 기회) |

---

## 🔧 Utilities & Maintenance (관리 도구)

데이터 정합성 유지 및 bulk 작업을 위한 도구들입니다.

### 과거 데이터 백필 (Backfill)
특정 기간의 데이터를 대량으로 수집하거나 다시 계산할 때 사용합니다.

```bash
# 1. 캔들 데이터 백필 (FDR + KRX)
uv run scripts/backfill_candles.py --start 2024-01-01 --end 2024-12-31

# 2. 지표 데이터 재계산 (DB 캔들 기준)
uv run scripts/backfill_indicators.py --start 2024-01-01 --end 2024-12-31

# 3. 시장 지수(KOSPI/KOSDAQ) 백필
uv run scripts/backfill_index.py --start 2024-01-01
```

### 누락 데이터 복구 (Missed Daily Data)
조기 실행 등으로 특정 거래일의 당일 시세가 누락된 경우, 익일 이후 다음 순서로 복구합니다. (KRX 공식 API에는 익일이면 데이터가 안정적으로 공시되어 있습니다.)

```bash
cd backend

# 1. 종목 마스터 갱신 (신규 상장 종목 FK 누락 방지)
uv run ../scripts/run_collector.py --mode tickers

# 2. 누락된 날짜를 각각 당일 시세 수집 (KRX 공식 API)
uv run ../scripts/run_collector.py --mode daily --date 2026-06-08
uv run ../scripts/run_collector.py --mode daily --date 2026-06-09

# 3. 해당 기간 지표 재계산
uv run ../scripts/backfill_indicators.py --start 2026-06-08 --end 2026-06-09

# 4. (선택) 해당 날짜 전략 신호 재스캔 및 텔레그램 발송
uv run ../scripts/run_strategy.py --date 2026-06-08
```

> 백필 검증: `daily_candles`와 `daily_technical_indicators`의 날짜별 건수가 정상 거래일과 동일한 수준(종목 수)인지 확인합니다.

### 데이터 검증 (Verify)

```bash
# DB 데이터 건수 및 상태 확인
uv run scripts/verify_db.py

# 지표 데이터 정합성 확인
uv run scripts/verify_indicators.py --start 2026-01-01
```

---

## 📂 Project Structure

```
backend/
├── app/
│   ├── api/v1/                # API 엔드포인트
│   ├── backtest/              # 백테스트 엔진 및 전략 클래스
│   │   ├── strategies/        # 개별 전략 구현체 (trend, sma 등)
│   │   └── engine.py          # 백테스트 코어 로직
│   ├── services/              # 비즈니스 로직 (수집, 계산 등)
│   │   ├── collector.py       # 당일 시세 수집(KRX 공식 API) 및 종목 마스터(FDR) 관리
│   │   ├── krx_collector.py   # KRX 공식 인증 API 수집기 (requests)
│   │   ├── hybrid_collector.py # FDR(수정주가) + KRX(거래대금/시총) 하이브리드 백필
│   │   ├── indicator_calculator.py # 기술적 지표 계산기
│   │   └── strategy_scanner.py # 전략 신호 스캐너
│   ├── core/
│   │   └── logger.py          # 공통 로거 (TREND_SURFER_SUBPROCESS 지원)
│   └── db/                    # DB 연결
├── scripts/                   # 실행 스크립트 (backend/ 상위에 위치)
│   ├── daily_routine.py       # [Daily] 일일 배치 메인 (자동화 진입점)
│   ├── run_collector.py       # 시세/종목 수집
│   ├── update_adjusted_prices.py # 수정주가 이벤트 감지 및 백필
│   ├── run_daily_indicators.py # 지표 계산
│   ├── update_warning_stocks.py # 경고종목 업데이트 (키움 REST API)
│   ├── run_strategy.py        # [Daily] 전략 신호 스캔
│   ├── run_backtest.py        # [Backtest] 백테스트 실행
│   ├── backfill_candles.py    # 과거 캔들 백필
│   └── backfill_indicators.py # 과거 지표 재계산
└── .env                       # 환경 변수 (비공개)
```

> **참고**: `scripts/`는 프로젝트 루트(`trend-surfer-claude/scripts/`)에 위치합니다. `backend/` 디렉토리에서 `uv run ../scripts/xxx.py`로 실행합니다.

---

## 📋 로깅 아키텍처

- 통합 로그 파일: `logs/trend_surfer_YYYYMMDD.log`
- `daily_routine.py`가 각 스크립트를 subprocess로 실행할 때 `TREND_SURFER_SUBPROCESS=1` 환경변수를 설정
- subprocess는 stdout에만 로그를 출력하고, daily_routine이 이를 순서대로 로그 파일에 기록 (파일 동시 쓰기 방지)
