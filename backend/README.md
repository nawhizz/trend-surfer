# TrendSurfer Backend

TrendSurfer의 백엔드 시스템입니다. **FastAPI**를 기반으로 구축되었으며, 한국 주식 시장(KOSPI, KOSDAQ)의 데이터를 수집하고 정량적 분석을 위한 API를 제공합니다.

## 🛠 기술 스택 (Tech Stack)

- **Framework**: FastAPI
- **Language**: Python 3.12+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Database**: Supabase (PostgreSQL)
- **Data Source**: FinanceDataReader (FDR)

## 🚀 시작하기 (Getting Started)

### 1. 환경 설정

`uv` 패키지 매니저가 설치되어 있어야 합니다.

```bash
# 프로젝트 의존성 설치
uv sync
```

### 2. 환경 변수 설정

`backend/.env` 파일을 생성하고 아래 내용을 설정하세요. (`.env.example` 참고)

```ini
SUPABASE_URL="YOUR_SUPABASE_URL"
SUPABASE_KEY="YOUR_SUPABASE_KEY"
KRX_API_KEY="YOUR_KRX_API_KEY"

```

### 3. 서버 실행

```bash
# 개발 모드 실행 (Hot Reload)
uv run uvicorn app.main:app --reload
```

서버가 실행되면 `http://localhost:8000`에서 접속할 수 있습니다.

## 📚 API 문서 (API Documentation)

서버 실행 후 아래 주소에서 Swagger UI를 통해 API 명세를 확인할 수 있습니다.

- **Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## 📦 데이터 수집 (Data Collection)

`FinanceDataReader`를 사용하여 KRX(한국거래소) 데이터를 수집합니다.

### 주요 기능
1.  **종목 리스트 수집 (`POST /api/v1/collect/stocks`)**
    - KOSPI, KOSDAQ 전 종목 수집
    - **Sector / Industry**: `KRX-DESC` 데이터를 병합하여 상세 업종(예: '통신 및 방송 장비 제조업') 및 주요 제품 정보(`Industry`) 저장
    - **우선주 식별**: Ticker가 '0'으로 끝나지 않는 경우 `is_preferred=True`로 자동 분류

2.  **일봉 데이터 수집 (`POST /api/v1/collect/daily`)**
    - **KRX Open API**를 사용하여 정확한 **거래대금(Trading Value)** 및 시가총액 수집
    - **거래대금 정의**: `종가 × 거래량` (KRX 공식 기준)
    - **Data Priority**: `KRX Amount` > `FDR Amount` (FDR 값이 있어도 KRX 데이터를 우선 사용)
    - 전 종목의 일별 OHLCV(시가/고가/저가/종가/거래량) 수집
    - KOSPI, KOSDAQ 시장 전체 데이터 일괄 처리

### 과거 데이터 백필 (Historical Data Backfill)
과거 데이터를 대량으로 수집하려면 `backfill_candles.py` 스크립트를 사용하세요. 
**FinanceDataReader(수정주가)**와 **KRX Open API(거래대금/시가총액)** 데이터를 병합하여, 정확하고 분석 친화적인 데이터를 구축합니다.
- **Failover Logic**: `FinanceDataReader`가 데이터를 가져오지 못하는 종목(예: 알파벳이 포함된 종목코드 등 34여 개)에 대해서는 자동으로 **KRX Open API 데이터로 대체(Fallback)**하여 데이터 누락을 방지합니다.

```bash
# 사용법: uv run scripts/backfill_candles.py --start [YYYY-MM-DD] --end [YYYY-MM-DD]

# 예: 2024년 1월 데이터 백필 (backend 디렉토리에서 실행)
cd backend
uv run ../scripts/backfill_candles.py --start 2024-01-01 --end 2024-01-31
```

### 수정주가 관리 (Adjusted Price Management)
KRX API를 활용하여 수정주가(액면분할, 합병 등) 이벤트를 자동으로 탐지하고 과거 데이터를 보정합니다.

**작동 원리**:
1. KRX API의 '대비(Change Amount)'를 통해 *시장이 인식하는 어제 종가*를 역산합니다.
2. DB에 저장된 *실제 어제 종가*와 비교하여 차이가 발생하면 수정주가 이벤트로 판단합니다.
3. 해당 종목에 대해 과거 1년치(기본값) 데이터를 자동으로 재수집(Backfill)합니다.

```bash
# 수정주가 자동 탐지 및 업데이트 (매일 마감 후 실행 권장)
cd backend
uv run ../scripts/update_adjusted_prices.py

# 특정 날짜 기준 실행 (테스트용)
uv run ../scripts/update_adjusted_prices.py --date 20240103
```

### 🔧 주요 유틸리티 (Scripts)

| 스크립트 | 설명 |
|----------|------|
| `run_backtest.py` | 전략 백테스트 실행 (SMA/EMA) |
| `backfill_candles.py` | 과거 캔들 데이터 대량 수집 |
| `update_adjusted_prices.py` | 수정주가 이벤트 감지 및 자동 보정 |
| `collect_today.py` | 당일(장 마감 후) 데이터 수집 |
| `calc_indicators.py` | 기술적 지표 수동 재계산 |
| `verify_db.py` | 데이터 정합성 검증 (종목 수, 누락 확인) |
| `check_market_filter.py` | 특정 날짜의 시장 필터 상태 확인 |


### 당일 데이터 수집 (Daily Data Collection)
KRX Open API의 데이터 지연(T+1) 문제를 보완하기 위해, `FinanceDataReader`의 실시간 스냅샷 기능을 활용하여 **오늘(당일)** 데이터를 적재합니다.

**작동 원리**:
- `fdr.StockListing('KRX')`를 호출하여 현재 시점의 시장 데이터를 가져옵니다.
- 장 마감(15:30) 이후 실행 시, 당일 종가와 정확한 거래대금(Amount)을 확보할 수 있습니다.
- **주의**: 이 데이터는 **실매매(Live Trading)**를 위한 것이며, 백테스트 시에는 **미래 데이터 누수(Look-Ahead Bias)** 방지를 위해 사용하지 않거나 주의해서 다뤄야 합니다. (백테스트는 T-1 기준)

```bash
# 오늘(장 마감 후) 데이터 적재
cd backend
uv run ../scripts/collect_today.py

# 특정 날짜(테스트 등 필요 시)
uv run ../scripts/collect_today.py --date 2026-01-12
```

### 수동 실행 스크립트
API 호출 외에도 스크립트를 통해 수집기를 직접 실행할 수 있습니다.

```bash
# 종목 리스트 수집 수동 실행
cd backend
uv run ../scripts/run_collector.py
```

## 📈 기술적 지표 계산 (Technical Indicators)

`ta-lib` 라이브러리를 사용하여 다양한 기술적 지표를 계산하고 DB에 저장합니다.

### 지원 지표

| 지표 | 기간 | 용도 |
|------|------|------|
| **SMA (단순이동평균)** | 5, 10, 20, 60, 120, 240일 | 추세 분석, 정배열 판단 |
| **EMA (지수이동평균)** | 5, 10, 20, 40, 50, 120, 200, 240일 | 추세 분석 |
| **ATR (평균 변동성)** | 20일 | 손절가, 포지션 사이징, 트레일링 스탑 |
| **HIGH (기간 최고 종가)** | 20일 | 신고가 돌파 신호 (당일 제외, Look-ahead bias 방지) |

### 계산 규칙 (Calculation Rules)
- **최소 데이터 요건**: 지표 계산을 위해 최소 `period` 이상의 데이터가 필요하며, 안정적인 값을 위해 일반적으로 더 긴 기간의 데이터를 로드하여 계산합니다.
- **NaN 처리**: 계산 초기의 NaN 값(Not a Number)은 DB에 저장하지 않습니다. 유효한 값(Valid Value)이 생성되는 시점부터 저장됩니다.

### 사용법

```bash
cd backend

# 계산 로직 테스트 (DB 저장 없음)
uv run ../scripts/calc_indicators.py --mode calc

# 단일 종목 (삼성전자) 계산 후 DB 저장
uv run ../scripts/calc_indicators.py --mode single --ticker 005930

# 여러 종목 처리
uv run ../scripts/calc_indicators.py --mode multi

# 추세추종 전략용 지표만 확인 (ATR, HIGH 중심)
uv run ../scripts/calc_indicators.py --mode strategy --ticker 005930
```

### 코드에서 사용

```python
from app.services.indicator_calculator import indicator_calculator

# 전체 활성 종목 처리
indicator_calculator.calculate_and_save_for_all_tickers(
    start_date="2025-01-01",
    end_date=None
)

# 특정 종목만 처리
indicator_calculator.calculate_and_save_for_all_tickers(
    start_date="2025-01-01",
    ticker_list=["005930", "000660"]
)
```

### 추세추종 전략용 지표

**정배열 + 20일 신고가 돌파** 전략에 필요한 지표들이 포함되어 있습니다.

| 전략 규칙 | 필요 지표 |
|-----------|----------|
| 정배열 판단 (`20MA > 60MA > 120MA`) | MA(20), MA(60), MA(120) |
| 20일 신고가 돌파 (`종가 > HIGH(20)`) | HIGH(20) |
| 손절가 (`진입가 - ATR × 2.5`) | ATR(20) |
| 트레일링 스탑 (`최고종가 - ATR × 3.0`) | ATR(20) |

### 시장 필터 (Market Regime Filter)

시장 전체가 역풍일 때 **신규 진입을 차단**하여 연속 손절과 계좌 변동성을 줄입니다.

**규칙**: `KOSPI 종가 > KOSPI 60MA AND KOSDAQ 종가 > KOSDAQ 60MA`

```bash
cd backend

# 지수 데이터 백필 (초기 1회)
uv run ../scripts/backfill_index.py --start 2024-01-01

# 시장 상태 확인 (단일 날짜)
uv run ../scripts/check_market_filter.py --mode status --date 2026-01-16

# 시장 상태 히스토리 (기간)
uv run ../scripts/check_market_filter.py --mode range --start 2026-01-01 --end 2026-01-16

# 지수 MA(60) 지표 DB 저장
uv run ../scripts/check_market_filter.py --mode save --start 2024-01-01
```

**코드에서 사용**:

```python
from app.services.market_filter import market_filter

# 특정 날짜 시장 필터 확인
if market_filter.is_bullish("2026-01-16"):
    print("신규 진입 허용")
else:
    print("신규 진입 금지")

# 상세 정보 조회
status = market_filter.get_market_status("2026-01-16")
print(status)
# {'kospi_close': 4840.74, 'kospi_ma60': 4145.98, 'is_bullish': True, ...}
```

### 과거 데이터 지표 백필 (Backfill Indicators)

DB에 저장된 과거 일봉 데이터를 바탕으로 기술적 지표를 계산하여 저장합니다.

```bash
cd backend

# 1. 전체 기간, 전체 종목 백필
uv run ../scripts/backfill_indicators.py

# 2. 특정 기간 백필
uv run ../scripts/backfill_indicators.py --start 2024-01-01 --end 2024-12-31

# 3. 특정 종목만 백필
uv run ../scripts/backfill_indicators.py --ticker 005930
```

### 지표 데이터 정합성 검증 (Verify Indicators)

저장된 지표 데이터의 건수를 확인하여 정합성을 검증합니다.

```bash
cd backend
uv run ../scripts/verify_indicators.py --start 2026-01-01 --end 2026-01-13
```

## 🗄️ 데이터베이스 스키마 (Database Schema)

`Supabase` (PostgreSQL)를 사용하며 주요 테이블은 다음과 같습니다.

- **stocks**: 종목 마스터 정보
    - `ticker`: 종목 코드 (PK)
    - `sector`: 업종 (예: 전기전자, 의약품)
    - `industry`: 상세 제품/산업 정보
    - `is_preferred`: 우선주 여부
- **daily_candles**: 일봉 데이터
    - `ticker`: 종목 코드 (FK)
    - `date`: 날짜
    - `change_rate`: 등락률
    - `market_cap`: 시가총액
- **indicator_metadata**: 지표 메타데이터
    - `indicator_type`: 지표 유형 (PK) - MA, EMA, RSI, MACD, BB 등
    - `required_params`: 필수 파라미터 정의 (JSONB)
    - `output_type`: 출력 유형 (single/multiple)
- **daily_technical_indicators**: 기술적 지표 (파라미터 기반)
    - `ticker`: 종목 코드 (FK, PK)
    - `date`: 날짜 (PK)
    - `indicator_type`: 지표 유형 (PK) - MA, EMA 등
    - `params`: 파라미터 (JSONB, PK) - `{"period": 5}` 등
    - `value`: 단일 값 지표용
    - `values`: 복합 값 지표용 (JSONB)

## 🛠 유틸리티 스크립트

- `scripts/verify_db.py`: 수집된 데이터(Row Count, 샘플 데이터) 검증
- `scripts/verify_preferred.py`: 우선주 로직 검증
- `scripts/debug_fdr.py`: FDR 데이터 소스 디버깅
- `test/test_indicator_calculator.py`: 기술적 지표 계산기 테스트 (MA/EMA/ATR/HIGH)
- `scripts/backfill_indicators.py`: 지표 데이터 백필
- `scripts/verify_indicators.py`: 지표 데이터 정합성 검증

```bash
# DB 데이터 검증
cd backend
uv run ../scripts/verify_db.py
```

## ⚠️ Data Integrity & Backtest Safety

본 시스템은 미래 데이터 누수(Future Leak)를 방지하기 위해 다음 원칙을 따릅니다.

- **T-1 원칙**: 모든 백테스트 및 전략 분석은 **T-1(어제 마감)** 기준 데이터를 사용해야 합니다.
- **실매매 원칙**: 장 마감 후 수집된 **당일 데이터**는 오직 실매매를 위한 **다음 거래일 시가 진입 신호 생성** 용도로만 사용해야 합니다.
- **지표 무결성**: 기술적 지표는 신뢰할 수 있는 최소 캔들 수 확보 후에만 저장 및 활용됩니다.
- **수정주가 보정**: 수정주가 이벤트 발생 시, 과거 데이터는 자동으로 재수집되어 항상 최신 수정주가 기준의 정합성을 유지합니다.

이를 통해 백테스트 결과와 실제 매매 성과 간의 괴리를 최소화합니다.

## � 백테스트 엔진 (Backtest Engine)

전략 백테스트를 위한 엔진입니다. Strategy 패턴을 적용하여 다양한 전략을 쉽게 추가할 수 있습니다.

### 지원 전략

| 전략 ID | 클래스명 | 설명 |
|---------|----------|------|
| `sma` | `SmaBreakoutStrategy` | SMA 정배열 (20MA > 60MA > 120MA) + 20일 신고가 돌파, 60MA 이탈 청산 |
| `ema` | `EmaBreakoutStrategy` | EMA 정배열 (20EMA > 50EMA > 120EMA) + 20일 신고가 돌파, 50EMA 이탈 청산 |

### CLI 사용법

```bash
cd backend

# SMA 전략 (기본)
uv run ../scripts/run_backtest.py --start 2025-01-01 --strategy sma

# EMA 전략
uv run ../scripts/run_backtest.py --start 2025-01-01 --strategy ema

# 특정 종목만 테스트
uv run ../scripts/run_backtest.py --start 2025-01-01 --ticker 005930,000660

# 결과 CSV 출력
uv run ../scripts/run_backtest.py --start 2025-01-01 --output ./results
```

### 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--start` | 시작일 (YYYY-MM-DD) | 필수 |
| `--end` | 종료일 (YYYY-MM-DD) | 오늘 |
| `--strategy` | 전략 선택 (sma/ema) | sma |
| `--ticker` | 특정 종목 (쉼표 구분) | 전체 활성 종목 |
| `--capital` | 초기 자본금 | 1억원 |
| `--risk` | 거래당 리스크 비율 | 0.01 (1%) |
| `--output` | CSV 출력 경로 | - |
| `--quiet` | 상세 로그 숨기기 | - |

### 파일 구조

```
backend/app/backtest/
├── engine.py              # 백테스트 엔진
├── portfolio.py           # 포트폴리오/포지션 관리
├── risk_manager.py        # 리스크 관리
├── result.py              # 결과 분석 및 통계
├── trade_repository.py    # DB 저장소
└── strategies/
    ├── base.py            # 전략 인터페이스
    ├── sma_breakout.py    # SMA 정배열 전략
    └── ema_breakout.py    # EMA 정배열 전략
```

### 코드에서 사용

```python
from app.backtest.engine import BacktestEngine
from app.backtest.strategies.sma_breakout import SmaBreakoutStrategy

# 전략 및 엔진 생성
strategy = SmaBreakoutStrategy()
engine = BacktestEngine(
    strategy=strategy,
    initial_capital=100_000_000,
    risk_per_trade=0.01,
    save_to_db=True,  # DB에 매매 기록 저장
)

# 백테스트 실행
result = engine.run(
    start_date="2025-01-01",
    end_date="2025-12-31",
    tickers=["005930", "000660"],
)

print(f"최종 자산: {result['final_equity']:,.0f}원")
print(f"거래 수: {len(result['trades'])}")
```

## �🕒 Daily Operation Flow (실운영 기준)

매일 장 마감 후 시스템 운영 흐름은 다음과 같습니다.

1.  **장 마감 (15:30 KST)**
2.  **당일 데이터 수집 & 정합성 검증**
    - `collect_today.py`: 오늘자 시세 및 정확한 거래대금(KRX) 적재
3.  **수정주가 이벤트 확인 및 백필**
    - `update_adjusted_prices.py`: 액면분할/합병 등 이벤트 감지 시 과거 데이터 자동 보정
4.  **기술적 지표 최신화**
    - `indicator_calculator`: 최신 캔들 기반 지표 업데이트
5.  **데이터 정합성 최종 확인** (Optional)
    - `verify_db.py`: 일자별 종목 수 및 데이터 상태 헬스체크
6.  **(Next Step) 전략 시그널 생성**
    - 적재된 데이터를 바탕으로 익일 매매 신호 생성

