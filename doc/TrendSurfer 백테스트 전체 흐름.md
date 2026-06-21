# TrendSurfer 백테스트 전체 흐름

`run_backtest.py` 실행에서 시작하여, 데이터 로드 → 일별 시뮬레이션 → 결과 분석/저장까지의 모든 단계를 정리한 문서입니다. ([일일 루틴 전체 흐름](./TrendSurfer%20일일%20루틴%20전체%20흐름.md)과 짝을 이루는 문서)

---

## 0단계: 진입점 — `run_backtest.py`

**명령 예시:**
```bash
cd backend
uv run ../scripts/run_backtest.py --start 2025-01-01 --strategy trend
uv run ../scripts/run_backtest.py --start 2024-01-01 --ticker 005930 --output ./results
```

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `--start` | (필수) | 시작일 (YYYY-MM-DD) |
| `--end` | 오늘 | 종료일 |
| `--ticker` | 전체 활성종목 | 특정 종목만 (쉼표 구분) |
| `--capital` | 100,000,000 | 초기 자본금(원) |
| `--risk` | 0.01 | 거래당 리스크 비율(1R) |
| `--strategy` | `sma` | `sma` / `ema` / `rsi` / `trend` |
| `--output` | - | 결과 CSV 출력 디렉토리 |
| `--quiet` | - | 상세 로그 숨김 |

처리 순서:
1. **종목 리스트 결정** — `--ticker` 지정 시 해당 종목, 미지정 시 `get_active_tickers()`로 전체 활성 보통주 조회
   - `stocks`에서 `is_active=True AND is_preferred=False AND market≠INDEX` (1000건 페이지네이션)
2. **전략 인스턴스 생성** — `--strategy` 값에 따라 4종 중 선택
3. **엔진 생성** (`BacktestEngine`) → `engine.run()` 실행
4. **결과 분석** (`BacktestResult`) → 통계 출력 + (옵션) CSV 저장

---

## 메인 엔진 — `BacktestEngine.run()`

`engine.run(start, end, tickers)`이 백테스트 전체를 오케스트레이션합니다.

1. **DB 세션 생성** (`save_to_db=True`일 때) — `backtest_sessions`에 전략명/기간/자본/리스크 기록, `session_id` 발급
2. **거래일 목록 조회** (`_get_trading_days`) — KOSPI 지수(`KS11`)의 캔들 날짜를 거래일 기준으로 사용
3. **데이터 프리로드** (`_preload_data`) — 종목별 캔들 + 지표를 한 번에 로드해 `SignalData`로 변환 후 캐시
4. **일별 시뮬레이션** — 모든 거래일에 대해 `_process_day()` 반복
5. **종료 시 강제 청산** (`_close_all_positions`) — 마지막 거래일 종가로 잔여 포지션 `FORCE_EXIT`
6. **결과 생성** (`_generate_result`) — 통계/거래/일별기록/리스크 상태 반환

> 💡 **핵심 거래일 정의:** 거래일은 `KS11`(KOSPI 지수) 캔들 존재 여부로 판단합니다. 따라서 지수 데이터(`backfill_index.py`)가 적재돼 있어야 백테스트가 동작합니다.

---

## 하루 처리 — `_process_day()`

거래일 하루를 다음 순서로 시뮬레이션합니다.

1. **전일 손절 추적 초기화** (`stopped_out_today` 클리어)
2. **시장 필터 체크** (`strategy.check_market_filter`) — 지수 구조 등 진입 허용 여부 판단
3. **대기 진입 처리** (`_process_pending_entries`) — 전일 발생 시그널을 **당일 시가**에 실제 매수
4. **기존 포지션 청산 체크** (`_process_exits`)
5. **신규 진입 시그널 스캔** (`_scan_entry_signals`) — 시장 필터 OK일 때만
6. **불타기 시그널 스캔** (`_scan_pyramid_signals`) — 추세추종 전략에서만
7. **일별 기록** (`portfolio.record_daily`) — 에러와 무관하게 항상 기록, 최고자산 갱신

> ⏱ **시그널-진입 시차:** 시그널은 종가 기준으로 당일 발생 → 다음 거래일 **시가**에 진입합니다(룩어헤드 편향 방지). 이를 위해 `PendingEntry` 큐를 사용합니다.

---

## 진입 로직 (3·5단계 상세)

### 신규 시그널 스캔 (`_scan_entry_signals`)
진입 차단 가드를 먼저 통과해야 합니다.

1. **Kill Switch** — 최근 10거래 중 8회 이상 실패 시 활성화, **20거래일간 신규 진입 중단** (쿨타임 경과 시 자동 해제)
2. **계좌 드로다운(DD) ≥ 15%** — 신규 진입 차단
3. 종목별 스킵 조건: 이미 보유 중 / 대기 큐에 있음 / 당일 손절됨 / **재진입 쿨타임 미충족**
4. `strategy.check_entry_signal()` 충족 → `PendingEntry` 큐에 추가 (익일 시가 진입 예정)

**재진입 규칙** (`_check_reentry_allowed`): 직전 청산 후 전략별 `RE_ENTRY_COOLDOWN`(기본 5거래일) 경과해야 재진입 허용.

### 대기 진입 처리 (`_process_pending_entries`)
당일 시가(`data.open`)로 실제 매수합니다.

1. 손절가 계산 (`strategy.calculate_stop_loss` = 진입가 − ATR × 배수)
2. **포지션 사이징** (`risk_manager.calculate_position_size`) — `수량 = (자본 × 리스크%) ÷ (진입가 − 손절가)`
3. **총 리스크 상한 체크** (`can_take_risk`) — 포트폴리오 총 리스크 ≤ 4%
4. **현금 확인** 후 부족하면 매수 가능 수량으로 축소
5. `portfolio.open_position()` → DB 매수 기록(`record_buy`)

---

## 청산 로직 — `_process_exits()`

보유 포지션마다:
1. **최고 종가 갱신** (`update_highest_close`) — 트레일링 스탑 기준
2. `strategy.check_exit_signal()` 호출 → 청산 사유 판정
   - `STOP_LOSS` (초기 손절), `TRAILING_STOP` (ATR 트레일링), `EMA_STRUCTURE_EXIT` (구조 붕괴) 등
3. 청산 시 `portfolio.close_position()` → DB 매도 기록(`record_sell`), 손익·R배수 계산
4. **후속 처리:**
   - 손절이면 `stopped_out_today`에 추가 (당일 재진입 금지)
   - 마지막 청산 정보 저장 (재진입 쿨타임용)
   - Kill Switch용 최근 거래 결과(승/패) 갱신
   - `risk_manager.on_trade_exit()` 호출

---

## 리스크 관리 — `RiskManager`

| 항목 | 값 | 설명 |
|------|----|------|
| 기본 리스크 | 1% (`risk_per_trade`) | 거래당 1R |
| 감축 리스크 | 0.5% | 감축 모드 시 적용 |
| 총 리스크 상한 | 4% | 동시 보유 포지션 합산 |
| **감축 트리거** | 3연속 손절 **또는** DD −7% | 이후 3거래 리스크 절반 |
| **복구 조건** | +2R 회복 **또는** 정상청산 2회 **또는** 감축거래 소진 | 기본 리스크 복귀 |

엔진 레벨의 추가 가드: **Kill Switch**(10중 8패 → 20일 중단), **DD ≥ 15% 진입 차단**.

---

## 결과 분석 — `BacktestResult`

`engine.run()` 결과를 받아 상세 통계를 계산·출력합니다.

**산출 지표:**
- 수익률: 총 수익률, **CAGR**(연평균)
- 거래: 총 거래 수, 승률, 평균 수익/손실, **손익비(Profit Factor)**, 평균 R배수
- 리스크: **최대 낙폭(MDD)** 및 발생일, **샤프 비율**(연율화 252일 기준)
- 기간: 평균 보유일, 최대 연속 승/패

**출력:**
- 콘솔: `print_summary()` 로 요약 표 출력
- CSV(`--output` 지정 시): `trades.csv`(거래 내역), `equity.csv`(자산 곡선) — `utf-8-sig` 인코딩

---

## 전체 데이터 흐름 요약

```
run_backtest.py (CLI)
   ├─ 종목 결정    : stocks → 활성 보통주 (또는 --ticker)
   ├─ 전략 생성    : sma / ema / rsi / trend
   └─ BacktestEngine.run()
        ├─ DB 세션 생성 : backtest_sessions (session_id)
        ├─ 거래일 조회  : KS11(KOSPI 지수) 캔들 날짜
        ├─ 데이터 로드  : daily_candles + indicators → SignalData 캐시
        ├─ 일별 루프 _process_day():
        │     ├─ 시장 필터 체크
        │     ├─ 대기 진입 → 당일 시가 매수 (+포지션 사이징/리스크 체크)
        │     ├─ 청산 체크 (손절/트레일링/구조)
        │     ├─ 신규 시그널 스캔 (Kill Switch·DD 가드 → PendingEntry)
        │     └─ 불타기 스캔 (trend 전략)
        ├─ 종료 강제청산 : FORCE_EXIT
        └─ 결과 생성
   └─ BacktestResult : 통계 출력 + (옵션) CSV 저장
```

**핵심 의존성:**
- 거래일은 `KS11` 지수 캔들로 정의 → **지수 데이터 적재 필수**
- 종목 캔들·지표가 비어 있으면 시그널이 발생하지 않음 → 사전 백필 필요 (`backfill_candles.py`, `backfill_indicators.py`)

---

## 지원 전략 (요약)

| ID | 클래스 | 진입 핵심 조건 |
|----|--------|----------------|
| `trend` | TrendFollowingStrategy | 20일 신고가 + 50EMA 기울기 ≥ -0.2 + ATR 과열 아님 (불타기 지원) |
| `sma` | SmaBreakoutStrategy | SMA(20/60/120) 정배열 + 신고가 돌파 |
| `ema` | EmaBreakoutStrategy | EMA(20/50/120) 정배열 + 신고가 돌파 |
| `rsi` | RsiSwingStrategy | RSI 눌림목 매수 + 과매수 청산 |

> 📄 추세추종 전략의 진입/청산 상세 규칙은 [전략 신호 스캔 조건 정리](./TrendSurfer%20전략%20신호%20스캔%20조건%20정리.md)의 "백테스트 전략과의 차이" 절을 참고하세요. (일일 스캐너와 백테스트 진입 조건이 다릅니다.)
