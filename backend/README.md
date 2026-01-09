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
    - 전 종목의 일별 OHLCV(시가/고가/저가/종가/거래량) 수집
    - **보조 지표**: `Change Rate`(등락률) 및 `Market Cap`(시가총액) 포함

### 수동 실행 스크립트
API 호출 외에도 스크립트를 통해 수집기를 직접 실행할 수 있습니다.

```bash
# 종목 리스트 수집 수동 실행
cd backend
uv run ../scripts/run_collector.py
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

## 🛠 유틸리티 스크립트

- `scripts/verify_db.py`: 수집된 데이터(Row Count, 샘플 데이터) 검증
- `scripts/verify_preferred.py`: 우선주 로직 검증
- `scripts/debug_fdr.py`: FDR 데이터 소스 디버깅

```bash
# DB 데이터 검증
cd backend
uv run ../scripts/verify_db.py
```
