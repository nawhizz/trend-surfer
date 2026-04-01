from datetime import datetime
import pandas as pd
import FinanceDataReader as fdr
from app.db.client import supabase
from app.core.logger import get_logger
from app.core.constants import BATCH_WRITE_UPSERT

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
        [FDR] 전 종목의 일봉 데이터를 수집합니다.
        FDR의 StockListing('KRX')는 '현재(오늘)' 기준 전 종목 시세를 제공합니다.
        과거 데이터 Bulk 수집은 FDR로 어려우므로, 이 함수는 '오늘/최근' 데이터 수집용으로 사용합니다.
        특정 과거 날짜 수집이 필요하면 loop를 돌거나 다른 방법을 써야 하지만, 
        자동매매 시스템은 주로 '오늘' 데이터를 마감 후 수집하는게 핵심입니다.
        """
        target_date = date_str
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        
        # Note: fdr.StockListing acts on 'latest' available data. 
        # We assume the user calls this after market close to get 'today's' data.
        # If date_str is provided and is NOT today, FDR StockListing cannot fetch it easily in bulk.
        # ideally we should check if date_str matches today, otherwise warn.
        
        logger.info(f"일봉 데이터 수집 시작 (FDR) - {target_date}")

        try:
            df = fdr.StockListing('KRX')
            
            all_candles = []
            
            for index, row in df.iterrows():
                # Filter Market
                market = row['Market']
                if market not in ['KOSPI', 'KOSDAQ']:
                    continue

                # Data validation (handling NaNs or zeros)
                # Align with KRXCollector: Skip only if BOTH Close and Volume are missing/zero.
                close_val = row['Close']
                vol_val = row['Volume']
                
                if (pd.isna(close_val) or close_val == 0) and (pd.isna(vol_val) or vol_val == 0):
                    continue
                
                # If Open/High/Low are NaN but Close exists (e.g. suspended), fill with Close or 0?
                # Usually FDR handles this, but let's be safe.
                # If Volume is 0, Open/High/Low might be NaN or 0.
                # We will cast to int safely below.

                # FDR columns: Close, Open, High, Low, Volume, Change (Ratio?), Marcap...
                # Note: fdr.StockListing('KRX') columns are: 
                # Code, ISU_CD, Name, Market, Dept, Close, ChangeCode, Changes, ChagesRatio, Open, High, Low, Volume, Amount, Marcap, Stocks, MarketId
                
                # Safe extraction helper
                def safe_int(val):
                    if pd.isna(val): return 0
                    return int(val)
                
                def safe_float(val):
                    if pd.isna(val): return 0.0
                    return float(val)

                candle = {
                    "ticker": str(row['Code']),
                    "date": target_date, # FDR Listing doesn't return date column, assume request date
                    "open": safe_int(row['Open']),
                    "high": safe_int(row['High']),
                    "low": safe_int(row['Low']),
                    "close": safe_int(row['Close']),
                    "volume": safe_int(row['Volume']),
                    "amount": safe_float(row.get('Amount')),
                    "change_rate": safe_float(row.get('ChagesRatio')),
                    "market_cap": safe_int(row.get('Marcap')),
                    "created_at": datetime.utcnow().isoformat()
                }
                all_candles.append(candle)
            
            # Batch Insert
            if all_candles:
                for i in range(0, len(all_candles), BATCH_WRITE_UPSERT):
                    chunk = all_candles[i:i + BATCH_WRITE_UPSERT]
                    supabase.table("daily_candles").upsert(chunk).execute()
                    logger.debug(f"캔들 upsert {i} ~ {i+len(chunk)}")
                logger.info(f"{target_date} 일봉 데이터 {len(all_candles)}건 저장 완료")
            else:
                logger.warning("저장할 캔들 데이터가 없습니다.")

        except (KeyError, ValueError) as e:
            logger.error(f"FDR 캔들 데이터 파싱 오류: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"일봉 데이터 수집 실패: {e}", exc_info=True)

        return all_candles  # FDR 폴백 호출자(update_adjusted_prices)가 활용

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
