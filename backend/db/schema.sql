-- TrendSurfer Schema (TRD v1.0 based)

-- 1. stocks (종목 마스터)
CREATE TABLE IF NOT EXISTS stocks (
    ticker VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    market VARCHAR(10) NOT NULL, -- KOSPI / KOSDAQ
    sector VARCHAR(100),
    industry VARCHAR(255),
    is_preferred BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Comments for stocks table
COMMENT ON TABLE stocks IS '종목 마스터 정보';
COMMENT ON COLUMN stocks.ticker IS '종목 코드 (PK)';
COMMENT ON COLUMN stocks.name IS '종목명';
COMMENT ON COLUMN stocks.market IS '시장 구분 (KOSPI/KOSDAQ)';
COMMENT ON COLUMN stocks.sector IS '업종/섹터';
COMMENT ON COLUMN stocks.industry IS '주요 제품/산업 (상세)';
COMMENT ON COLUMN stocks.is_preferred IS '우선주 여부 (True: 우선주)';
COMMENT ON COLUMN stocks.is_active IS '거래 가능 여부 (False: 상장폐지 등)';
COMMENT ON COLUMN stocks.created_at IS '생성 일시';
COMMENT ON COLUMN stocks.updated_at IS '수정 일시';


-- 2. daily_candles (일봉 데이터)
CREATE TABLE IF NOT EXISTS daily_candles (
    ticker VARCHAR(20) NOT NULL REFERENCES stocks(ticker) ON DELETE CASCADE,
    date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    change_rate NUMERIC,
    volume BIGINT,
    amount NUMERIC,
    market_cap BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_candles_ticker_date ON daily_candles(ticker, date DESC);

-- Comments for daily_candles table
COMMENT ON TABLE daily_candles IS '일봉(Daily Candle) 데이터';
COMMENT ON COLUMN daily_candles.ticker IS '종목 코드 (FK, PK)';
COMMENT ON COLUMN daily_candles.date IS '거래 일자 (PK)';
COMMENT ON COLUMN daily_candles.open IS '시가';
COMMENT ON COLUMN daily_candles.high IS '고가';
COMMENT ON COLUMN daily_candles.low IS '저가';
COMMENT ON COLUMN daily_candles.close IS '종가';
COMMENT ON COLUMN daily_candles.change_rate IS '등락률';
COMMENT ON COLUMN daily_candles.volume IS '거래량';
COMMENT ON COLUMN daily_candles.amount IS '거래대금';
COMMENT ON COLUMN daily_candles.market_cap IS '시가총액';
COMMENT ON COLUMN daily_candles.created_at IS '생성 일시';


-- 3. indicator_metadata (지표 메타데이터)
-- 지표 유형과 필수 파라미터 정의를 관리하는 테이블
CREATE TABLE IF NOT EXISTS indicator_metadata (
    indicator_type VARCHAR(30) PRIMARY KEY,
    description TEXT,
    required_params JSONB,        -- 필수 파라미터 정의: {"period": "int"} 또는 {"short": "int", "long": "int", "signal": "int"}
    output_type VARCHAR(20)       -- 'single' (단일 값) 또는 'multiple' (복합 값)
);

-- Comments for indicator_metadata table
COMMENT ON TABLE indicator_metadata IS '기술적 지표 메타데이터 (지표 유형 및 파라미터 정의)';
COMMENT ON COLUMN indicator_metadata.indicator_type IS '지표 유형 코드 (PK): MA, EMA, RSI, MACD, BB 등';
COMMENT ON COLUMN indicator_metadata.description IS '지표 설명';
COMMENT ON COLUMN indicator_metadata.required_params IS '필수 파라미터 정의 (JSONB)';
COMMENT ON COLUMN indicator_metadata.output_type IS '출력 유형: single(단일값) 또는 multiple(복합값)';

-- 기본 지표 메타데이터 삽입
INSERT INTO indicator_metadata (indicator_type, description, required_params, output_type) VALUES
    ('MA', '단순 이동평균 (Simple Moving Average)', '{"period": "int"}', 'single'),
    ('EMA', '지수 이동평균 (Exponential Moving Average)', '{"period": "int"}', 'single'),
    ('RSI', '상대강도지수 (Relative Strength Index)', '{"period": "int"}', 'single'),
    ('MACD', 'MACD (Moving Average Convergence Divergence)', '{"short": "int", "long": "int", "signal": "int"}', 'multiple'),
    ('BB', '볼린저 밴드 (Bollinger Bands)', '{"period": "int", "std": "float"}', 'multiple')
ON CONFLICT (indicator_type) DO NOTHING;


-- 4. daily_technical_indicators (기술적 지표 - 파라미터 기반)
-- 유연한 구조로 새 지표/파라미터 추가 시 스키마 변경 불필요
CREATE TABLE IF NOT EXISTS daily_technical_indicators (
    ticker VARCHAR(20) NOT NULL REFERENCES stocks(ticker) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- 지표 식별
    indicator_type VARCHAR(30) NOT NULL,  -- 'MA', 'EMA', 'RSI', 'MACD', 'BB' 등
    params JSONB NOT NULL DEFAULT '{}',   -- 파라미터: {"period": 5} 또는 {"short": 12, "long": 26, "signal": 9}
    
    -- 지표 값
    value NUMERIC,                         -- 단일 값 지표용 (MA, EMA, RSI)
    values JSONB,                          -- 복합 값 지표용 (MACD: {"macd": x, "signal": y, "hist": z})
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    
    PRIMARY KEY (ticker, date, indicator_type, params)
);

-- 조회 성능을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_tech_ticker_date ON daily_technical_indicators(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_tech_indicator_type ON daily_technical_indicators(indicator_type);
CREATE INDEX IF NOT EXISTS idx_tech_params ON daily_technical_indicators USING GIN (params);

-- Comments for daily_technical_indicators table
COMMENT ON TABLE daily_technical_indicators IS '일봉 기반 기술적 지표 데이터 (파라미터 기반 유연 구조)';
COMMENT ON COLUMN daily_technical_indicators.ticker IS '종목 코드 (FK, PK)';
COMMENT ON COLUMN daily_technical_indicators.date IS '기준 일자 (PK)';
COMMENT ON COLUMN daily_technical_indicators.indicator_type IS '지표 유형: MA, EMA, RSI, MACD, BB 등 (PK)';
COMMENT ON COLUMN daily_technical_indicators.params IS '지표 파라미터 (JSONB, PK): {"period": 5} 또는 {"short": 12, "long": 26, "signal": 9}';
COMMENT ON COLUMN daily_technical_indicators.value IS '단일 값 지표 결과 (MA, EMA, RSI 등)';
COMMENT ON COLUMN daily_technical_indicators.values IS '복합 값 지표 결과 (JSONB): MACD는 {"macd": x, "signal": y, "hist": z}, BB는 {"upper": x, "middle": y, "lower": z}';
COMMENT ON COLUMN daily_technical_indicators.created_at IS '생성 일시';


-- 업데이트 시간 자동 갱신을 위한 함수 및 트리거 (선택사항)
-- CREATE OR REPLACE FUNCTION update_updated_at_column()
-- RETURNS TRIGGER AS $$
-- BEGIN
--    NEW.updated_at = now();
--    RETURN NEW;
-- END;
-- $$ language 'plpgsql';

-- CREATE TRIGGER update_stocks_updated_at
-- BEFORE UPDATE ON stocks
-- FOR EACH ROW
-- EXECUTE PROCEDURE update_updated_at_column();
