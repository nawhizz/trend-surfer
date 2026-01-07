# Technical Requirements Document (TRD): TrendSurfer

## 1. 기술 개요 (Technical Overview)
- **목표:** 대량의 주식 데이터(Tick/Daily)를 안정적으로 수집/가공하고, 사용자 정의 조건에 따라 실시간에 준하는 스크리닝을 수행하는 고성능 퀀트 백엔드 구축.
- **핵심 기술 과제:**
  - Python `uv`를 활용한 효율적인 패키지/가상환경 관리.
  - `FastAPI`의 비동기(Async) 처리를 통한 대량 데이터 수집 속도 최적화.
  - `Supabase`를 활용한 관계형 데이터 저장 및 `Next.js`와의 빠른 연동.

## 2. 시스템 아키텍처 (System Architecture)

### [Flow Diagram Overview]
`Data Sources (KRX/Naver/Kiwoom)` <--(Fetch)-- `FastAPI Server` --(Write/Read)--> `Supabase (PostgreSQL)`
                                                                    ^
`n8n (Scheduler/Trigger)` --(Webhook)--> `FastAPI Server`           |
                                                                    v
`User` <--(View)-- `Next.js Dashboard` <--(Query)-- `Supabase` / `FastAPI`
       <--(Notification)-- `Messenger (Telegram/Slack)`

- **핵심 컴포넌트:**
  - **Collector Engine (FastAPI):** `pykrx`, `FinanceDataReader` 등을 이용해 데이터 수집.
  - **Analysis Engine (FastAPI + TA-Lib):** 수집된 데이터로 기술적 지표 계산.
  - **Orchestrator (n8n):** 정해진 시간(장마감, 장중 12시 등)에 API를 호출하여 작업 트리거.

## 3. 기술 스택 (Technology Stack)
| 구분 | 기술 / 라이브러리 | 선택 사유 |
|---|---|---|
| **프론트엔드** | **Next.js (App Router)** | 서버 사이드 렌더링(SSR)을 통한 빠른 데이터 조회, Supabase와 호환성 우수. |
| **백엔드** | **Python 3.10+, FastAPI** | 고성능 비동기 처리 지원, 데이터 분석 라이브러리(Pandas, TA-Lib) 활용 용이. |
| **패키지 관리** | **uv** | `pip`보다 압도적으로 빠른 설치 속도 및 가상환경 관리. |
| **데이터베이스** | **Supabase (PostgreSQL)** | 관리형 DB, 별도 백엔드 없이 프론트에서 조회 가능(Row Level Security), 백업 용이. |
| **데이터 수집** | **pykrx, FinanceDataReader** | 한국 주식 시장 데이터 무료 수집 (일봉, 기본정보). |
| **실시간/상세** | **Naver Fin (Crawling), Kiwoom API** | 장중 실시간 시세 파악 및 추후 실주문 연동용. |
| **지표 계산** | **TA-Lib** | C언어 기반의 고성능 기술적 분석 라이브러리 ($RSI$, $MACD$, $Bollinger$ 등). |
| **자동화** | **n8n** | 복잡한 크론잡(Cronjob) 대체, 시각적 워크플로우 관리, 알림 발송 연동 용이. |

## 4. 데이터 모델 (Data Model - ERD Draft)

### `stocks` (종목 마스터)
- `ticker` (PK, varchar): 종목 코드 (예: 005930)
- `name` (varchar): 종목명 (예: 삼성전자)
- `market` (varchar): KOSPI / KOSDAQ
- `sector` (varchar): 업종
- `is_preferred` (boolean): 우선주 여부 (True: 우선주, False: 보통주)
- `is_active` (boolean): 상장 폐지 여부 등 관리

### `daily_candles` (일봉 데이터)
- `id` (PK, bigint): Auto Increment
- `ticker` (FK): 종목 코드
- `date` (date): 기준 일자
- `open`, `high`, `low`, `close` (numeric): 시가, 고가, 저가, 종가
- `volume` (bigint): 거래량
- `amount` (numeric): 거래대금
- **Index:** `(ticker, date)` 복합 인덱스 (조회 성능 필수)

### `daily_technical_indicators` (기술적 지표 - 별도 테이블로 분리하여 관리 추천)
- `id` (PK): Auto Increment
- `ticker` (FK), `date` (FK)
- `ma_5`, `ma_20`, `ma_60` (numeric): 이동평균선
- `rsi_14` (numeric): RSI
- `macd`, `macd_signal`, `macd_hist` (numeric): MACD
- `created_at` (timestamp): 계산 시점

## 5. API 명세 (Key Endpoints - FastAPI)

- **데이터 수집 제어**
  - `POST /api/v1/jobs/collect/daily`: (n8n 트리거) 전 종목 일봉 데이터 수집 및 저장.
  - `POST /api/v1/jobs/collect/realtime`: (n8n 트리거) 장중 특정 종목군 현재가 업데이트.

- **분석 및 스크리닝**
  - `POST /api/v1/analysis/calculate`: 저장된 캔들 데이터로 TA-Lib 지표 일괄 계산.
  - `GET /api/v1/screen/intraday`: 현재 시점 기준 전략 조건(예: 거래량 급증 + RSI < 30) 만족 종목 반환.

- **프론트엔드 연동**
  - `GET /api/v1/stocks/{ticker}`: 특정 종목 상세 정보 및 지표 조회.

## 6. 개발 폴더 구조 (Project Structure)
*유지보수와 확장성을 고려한 Monorepo 스타일의 구조를 제안합니다.*
*우선은 개략적인 구조만 제안*

```text
trend-surfer/
├── backend/                   # FastAPI Server
│   ├── app/
│   │   ├── api/               # API 엔드포인트 라우팅
│   │   ├── core/              # 핵심 설정 (config, security)
│   │   ├── db/                # 데이터베이스 처리
│   │   ├── services/          # 비즈니스 로직 (핵심)
│   │   ├── schemas/           # Pydantic 데이터 모델 (DTO)
│   │   └── main.py            # 앱 진입점
│   ├── tests/                 # 단위/통합 테스트
│   └── .env                   # 백엔드 환경변수
│
├── frontend/                  # Next.js Dashboard
│   ├── src/
│   │   ├── app/               # App Router (페이지)
│   │   ├── components/        # UI 컴포넌트
│   │   ├── lib/               # 유틸리티 및 라이브러리
│   │   └── types/             # TypeScript 타입 정의
│   └── .env.local             # 프론트엔드 환경변수
├── data/                      # 로컬 테스트용 데이터 (git ignore)
└── README.md                  # 프로젝트 설명서
```

## 7. 개발 및 배포 환경 (DevOps)
- **로컬 개발:** `uv`를 이용한 가상환경(`python -m uv venv`), Docker Compose로 로컬 Supabase(선택) 구동.
- **인프라:**
  - **Backend:** 24시간 가동 서버 필요 (AWS EC2 Free Tier 혹은 Oracle Cloud Free Tier 추천, *초기에는 로컬 PC 활용 가능성 높음*).
  - **Frontend:** Vercel (Next.js 최적화 배포).
- **자동화:** Github Actions를 통해 `main` 브랜치 푸시 시 자동 테스트 및 배포.

## 8. 주요 리스크 및 해결 방안
- **리스크 1:** 장중 전 종목 스크리닝 시 API 요청 제한(Rate Limit) 걸림.
  - **해결:** `pykrx` 등 스크래핑 방식은 장중 느릴 수 있음. 장중에는 네이버 금융 크롤링(비동기) 혹은 키움 API(TR 제한 주의)를 혼용. 관심 종목군을 먼저 필터링하여 대상 종목 수 줄이기.
- **리스크 2:** TA-Lib 설치 호환성 문제.
  - **해결:** `uv` 사용 시 바이너리 빌드 문제 발생 가능. Dockerfile 작성 시 TA-Lib 공식 빌드 과정을 포함하거나, `talib-binary` 휠 사용 고려.

## 9. 개발 마일스톤
- **Week 1:** FastAPI + Supabase 환경 설정, `stocks` 및 `daily_candles` 수집기 구현.
- **Week 2:** TA-Lib 연동 지표 계산 로직 구현, n8n 스케줄러 등록.
- **Week 3:** 장중 스크리닝 로직(12~14시) 개발 및 텔레그램 알림 연동.
- **Week 4:** Next.js 대시보드 개발 (차트 시각화) 및 MVP 배포.