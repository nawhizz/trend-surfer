from datetime import datetime
import pandas as pd
import FinanceDataReader as fdr
from app.db.client import supabase
from app.core.logger import get_logger
from app.core.constants import BATCH_WRITE_UPSERT
from app.services.krx_collector import krx_collector

logger = get_logger(__name__)

class StockCollector:
    def __init__(self):
        pass

    def update_stock_list(self):
        """
        [FDR] 전 종목 목록(Ticker, Name)을 최신화합니다.
        fdr.StockListing('KRX') 사용
        """
        logger.info("종목 마스터 업데이트 시작 (FDR)...")

        try:
            # KRX returns both KOSPI and KOSDAQ with price info
            df = fdr.StockListing('KRX')
            logger.info(f"KRX에서 {len(df)}개 종목 조회 완료")

            # KRX-DESC contains detailed Sector info
            try:
                df_desc = fdr.StockListing('KRX-DESC')
                logger.info(f"KRX-DESC에서 {len(df_desc)}개 종목 섹터 정보 조회 완료")
                desc_map = df_desc.set_index('Code')[['Sector', 'Industry']].to_dict('index')
                logger.debug(f"Desc Map 크기: {len(desc_map)}")
            except (KeyError, ValueError) as e:
                logger.warning(f"KRX-DESC 데이터 파싱 실패: {e}")
                desc_map = {}
            except Exception as e:
                logger.warning(f"KRX-DESC 조회 실패: {e}")
                desc_map = {}
            
            all_stocks = []
            
            # DataFrame columns: Code, Name, Market, Dept, Close, ...
            for index, row in df.iterrows():
                market = row['Market']
                if market not in ['KOSPI', 'KOSDAQ']:
                    continue

                ticker = str(row['Code'])
                
                # 우선주/신주인수권증서(Warrant) 판정
                # - 6자리 숫자가 아닌 경우 (W, R 등 문자 포함): 신주인수권증서 등 단기 파생 종목
                # - 6자리 숫자이나 끝자리가 0이 아닌 경우: 우선주
                is_preferred = not ticker.isdigit() or len(ticker) != 6 or not ticker.endswith('0')
                
                # Sector & Industry Logic: Use KRX-DESC if available
                desc_info = desc_map.get(ticker, {})
                sector = desc_info.get('Sector')
                industry = desc_info.get('Industry')
                
                # Handle NaN
                if pd.isna(sector): sector = None
                if pd.isna(industry): industry = None

                # Fallback for sector from 'Dept'
                if not sector and 'Dept' in row:
                     dept = row['Dept']
                     if not pd.isna(dept):
                         sector = dept

                stock_data = {
                    "ticker": ticker, 
                    "name": row['Name'],
                    "market": market,
                    "sector": sector,
                    "industry": industry,
                    "is_preferred": is_preferred,
                    # "is_active": True, # Removed simplistic assumption if needed, but let's keep True for now
                    "is_active": not (pd.isna(row['Close']) or row['Close'] == 0), # Simple active check
                    "updated_at": datetime.utcnow().isoformat()
                }
                all_stocks.append(stock_data)
            
            # Batch Upsert
            if all_stocks:
                for i in range(0, len(all_stocks), BATCH_WRITE_UPSERT):
                    chunk = all_stocks[i:i + BATCH_WRITE_UPSERT]
                    supabase.table("stocks").upsert(chunk).execute()
                    logger.debug(f"종목 upsert {i} ~ {i+len(chunk)}")
                logger.info("종목 마스터 업데이트 완료")

                # Deactivate delisted stocks (not in FDR anymore)
                # not_.in_()은 종목 수가 많으면 URI Too Long(414) 에러 발생
                # → DB 활성 종목을 먼저 조회 후 Python에서 차집합 계산, 개별 비활성화
                fdr_ticker_set = {stock['ticker'] for stock in all_stocks}
                try:
                    db_resp = supabase.table("stocks").select("ticker").eq("is_active", True).execute()
                    db_active = {row['ticker'] for row in db_resp.data}
                    delisted = db_active - fdr_ticker_set

                    if delisted:
                        for ticker in delisted:
                            supabase.table("stocks").update({"is_active": False}).eq("ticker", ticker).execute()
                        logger.info(f"상장폐지 종목 {len(delisted)}개 비활성화: {sorted(delisted)}")
                    else:
                        logger.info("상장폐지 종목 없음")
                except Exception as e:
                    logger.warning(f"상장폐지 종목 비활성화 실패: {e}")
            else:
                logger.warning("업데이트할 종목이 없습니다.")

        except (KeyError, ValueError) as e:
            logger.error(f"FDR 데이터 파싱 오류: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"종목 마스터 업데이트 실패: {e}", exc_info=True)

    def fetch_daily_ohlcv(self, date_str: str = None):
        """
        [KRX 공식 API] 전 종목의 일봉 데이터를 수집해 DB에 저장합니다.

        과거에는 FDR(`fdr.StockListing('KRX')`)을 사용했으나, FDR이 의존하는 외부
        GitHub 캐시 저장소의 갱신 지연으로 당일 데이터에서 HTTP 404가 빈번하게 발생했습니다.
        프로젝트에 이미 존재하는 KRX 공식 인증 API(`krx_collector`)가 장중에도 안정적이므로
        이를 사용하도록 전환했습니다.

        Args:
            date_str (str, optional): 대상일 (YYYY-MM-DD). None이면 오늘.

        Returns:
            list[dict]: 수집한 캔들 리스트 (호출자가 활용 가능). 데이터 없으면 빈 리스트.
        """
        target_date = date_str
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"일봉 데이터 수집 시작 (KRX) - {target_date}")

        # KRX API는 YYYYMMDD 형식을 사용
        api_date = target_date.replace("-", "")

        all_candles = krx_collector.fetch_market_ohlcv_by_date(api_date)

        if not all_candles:
            logger.warning(f"{target_date} KRX 일봉 데이터 없음 (휴장일 또는 데이터 미공시)")
            return []

        # KRX API는 ETF/ETN/스팩 등 stocks 마스터에 없는 종목도 반환하므로,
        # FK 제약(daily_candles_ticker_fkey) 위반을 막기 위해 DB 등록 종목으로 필터링
        try:
            db_tickers = set()
            offset, limit = 0, 1000
            while True:
                resp = supabase.table("stocks").select("ticker").range(offset, offset + limit - 1).execute()
                rows = resp.data
                if not rows:
                    break
                db_tickers.update(item['ticker'] for item in rows)
                offset += limit
                if len(rows) < limit:
                    break
        except Exception as e:
            logger.error(f"종목 마스터 조회 실패, 일봉 저장 중단: {e}", exc_info=True)
            return all_candles

        before = len(all_candles)
        all_candles = [c for c in all_candles if c['ticker'] in db_tickers]
        logger.info(f"DB 등록 종목 기준 {len(all_candles)}건 (전체 {before}건 중)")

        if not all_candles:
            logger.warning("DB 등록 종목과 일치하는 캔들이 없습니다.")
            return []

        # Batch Upsert (ticker/date 충돌 시 갱신)
        try:
            for i in range(0, len(all_candles), BATCH_WRITE_UPSERT):
                chunk = all_candles[i:i + BATCH_WRITE_UPSERT]
                supabase.table("daily_candles").upsert(chunk, on_conflict="ticker, date").execute()
                logger.debug(f"캔들 upsert {i} ~ {i+len(chunk)}")
            logger.info(f"{target_date} 일봉 데이터 {len(all_candles)}건 저장 완료")
        except Exception as e:
            logger.error(f"일봉 데이터 저장 실패: {e}", exc_info=True)

        return all_candles

    def fetch_historical_candles(self, start_date: str, end_date: str, ticker: str = None):
        """
        [FDR] 특정 기간의 일봉 데이터를 수집합니다. (FDR DataReader 사용)
        
        Args:
            start_date (str): 시작일 (YYYY-MM-DD)
            end_date (str): 종료일 (YYYY-MM-DD)
            ticker (str, optional): 특정 종목 코드. None이면 전체 활성 종목 대상.
        """
        logger.info(f"과거 캔들 수집 시작 ({start_date} ~ {end_date})")
        
        target_tickers = []
        if ticker:
            target_tickers = [ticker]
        else:
            # Fetch all active tickers from DB
            try:
                response = supabase.table("stocks").select("ticker").eq("is_active", True).execute()
                target_tickers = [item['ticker'] for item in response.data]
                logger.info(f"활성 종목 {len(target_tickers)}개 조회 완료")
            except Exception as e:
                logger.error(f"활성 종목 조회 실패: {e}", exc_info=True)
                return

        total_count = len(target_tickers)
        for idx, code in enumerate(target_tickers):
            try:
                # fdr.DataReader returns DataFrame with Index as Date
                df = fdr.DataReader(code, start_date, end_date)
                
                if df.empty:
                    logger.debug(f"[{idx+1}/{total_count}] {code}: 데이터 없음")
                    continue

                candles = []
                for date_idx, row in df.iterrows():
                    # Check for NaNs or invalid data in critical columns
                    if pd.isna(row['Open']) or pd.isna(row['Close']):
                        continue
                        
                    # Calculate Change Rate (FDR Change is simple ratio, e.g. 0.015 for 1.5%)
                    # We store percentage (e.g., 1.5) or ratio? 
                    # Existing fetch_daily_ohlcv uses 'ChagesRatio' directly from Listing which is usually percentage.
                    # FDR DataReader 'Change' is usually ratio (0.015). Let's convert to Percentage to be consistent with common display,
                    # BUT need to verify what 'ChagesRatio' in existing code does.
                    # In existing code: "change_rate": float(row['ChagesRatio']) ...
                    # Let's assume schema expects percentage. 
                    # If FDR DataReader Change is 0.01 -> 1.0%
                    
                    change_val = 0.0
                    if 'Change' in row and not pd.isna(row['Change']):
                        change_val = float(row['Change']) * 100
                    
                    # Amount estimation if missing
                    # FDR DataReader usually has 'Close', 'Open', 'High', 'Low', 'Volume', 'Change'
                    # Rarely 'Amount' (Transaction Value). If missing, Close * Volume
                    vol = int(row['Volume'])
                    close = int(row['Close'])
                    amount = float(row['Amount']) if 'Amount' in row else float(close * vol)
                    
                    # Market Cap is usually not in DataReader daily history, maybe in Listing. 
                    # We can leave it 0 or nullable. Daily candle schema has market_cap.
                    # We will leave it 0 as it's hard to get historical market cap accurately from basic fdr.DataReader call without Marcap lib
                    
                    candle = {
                        "ticker": code,
                        "date": date_idx.strftime("%Y-%m-%d"),
                        "open": int(row['Open']),
                        "high": int(row['High']),
                        "low": int(row['Low']),
                        "close": close,
                        "volume": vol,
                        "amount": amount,
                        "change_rate": change_val,
                        "market_cap": 0, # Not available in standard DataReader history
                        "created_at": datetime.utcnow().isoformat()
                    }
                    candles.append(candle)

                if candles:
                    supabase.table("daily_candles").upsert(candles).execute()
                    logger.debug(f"[{idx+1}/{total_count}] {code}: {len(candles)}건 저장")
                else:
                    logger.debug(f"[{idx+1}/{total_count}] {code}: 유효 데이터 없음")

            except (KeyError, ValueError) as e:
                logger.warning(f"[{idx+1}/{total_count}] {code} 데이터 파싱 오류: {e}")
            except Exception as e:
                logger.error(f"[{idx+1}/{total_count}] {code} 처리 실패: {e}")


collector = StockCollector()
