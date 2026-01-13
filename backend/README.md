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
    - 전 종목의 일별 OHLCV(시가/고가/저가/종가/거래량) 수집
    - KOSPI, KOSDAQ 시장 전체 데이터 일괄 처리

### 과거 데이터 백필 (Historical Data Backfill)
과거 데이터를 대량으로 수집하려면 `backfill_candles.py` 스크립트를 사용하세요. KRX Open API를 통해 시장 전체 데이터를 일자별로 효율적으로 수집합니다.

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

```

### 당일 데이터 수집 (Daily Data Collection)
KRX Open API의 데이터 지연(T+1) 문제를 보완하기 위해, `FinanceDataReader`의 실시간 스냅샷 기능을 활용하여 **오늘(당일)** 데이터를 적재합니다.

**작동 원리**:
- `fdr.StockListing('KRX')`를 호출하여 현재 시점의 시장 데이터를 가져옵니다.
- 장 마감(15:30) 이후 실행 시, 당일 종가와 정확한 거래대금(Amount)을 확보할 수 있습니다.

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

| 지표 | 기간 |
|------|------|
| **SMA (단순이동평균)** | 5, 10, 20, 60, 120, 240일 |
| **EMA (지수이동평균)** | 5, 10, 20, 40, 50, 120, 200, 240일 |

### 사용법

```bash
cd backend

# 계산 테스트 (DB 저장 없음)
uv run python test/test_indicator_calculator.py --mode calc

# 단일 종목 (삼성전자) 계산 후 DB 저장
uv run python test/test_indicator_calculator.py --mode single

# 여러 종목 처리
uv run python test/test_indicator_calculator.py --mode multi
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
- `test/test_indicator_calculator.py`: 이동평균 계산기 테스트

```bash
# DB 데이터 검증
cd backend
uv run ../scripts/verify_db.py
```
