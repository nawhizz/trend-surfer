from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd
import time

import FinanceDataReader as fdr

def get_all_market_data(start_date, end_date, market='ALL'):
    """
    KOSPI, KOSDAQ 전체 종목의 일별 주가 데이터 수집
    
    Parameters:
    - start_date: 시작일 (YYYYMMDD 형식의 문자열)
    - end_date: 종료일 (YYYYMMDD 형식의 문자열)
    - market: 'KOSPI', 'KOSDAQ', 'ALL' 중 선택
    
    Returns:
    - DataFrame: 전체 종목의 일별 주가 데이터
    """
    
    all_data = []
    
    # 시장 선택
    if market == 'ALL':
        markets = ['KOSPI', 'KOSDAQ']
    else:
        markets = [market]
    
    for mkt in markets:
        print(f"\n{mkt} 시장 데이터 수집 중...")
        
        # 해당 시장의 전체 종목 코드 가져오기 (FinanceDataReader 사용)
        try:
            # FDR에서는 'KOSPI', 'KOSDAQ' 문자열을 그대로 사용 가능
            df_master = fdr.StockListing(mkt)
            ticker_list = df_master['Code'].tolist()
            # 종목명 맵핑을 위해 딕셔너리 생성
            name_map = df_master.set_index('Code')['Name'].to_dict()
        except Exception as e:
            print(f"  {mkt} 종목 목록 수집 실패: {str(e)}")
            continue
        
        print(f"{mkt} 종목 수: {len(ticker_list)}개")
        
        # 각 종목별 데이터 수집
        for i, ticker in enumerate(ticker_list):
            try:
                # 종목명 가져오기 (FDR 데이터 활용)
                ticker_name = name_map.get(ticker, "Unknown")
                
                # 일별 주가 데이터 가져오기 (Pykrx)
                df = stock.get_market_ohlcv(start_date, end_date, ticker)
                
                if not df.empty:
                    df['종목코드'] = ticker
                    df['종목명'] = ticker_name
                    df['시장'] = mkt
                    df.reset_index(inplace=True)
                    df.rename(columns={'날짜': '일자'}, inplace=True)
                    all_data.append(df)
                
                # 진행상황 출력
                if (i + 1) % 50 == 0:
                    print(f"  진행: {i+1}/{len(ticker_list)} 종목 완료")
                
                # API 호출 제한을 위한 짧은 대기
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  오류 발생 - {ticker} ({ticker_name}): {str(e)}")
                continue
    
    # 전체 데이터 결합
    if all_data:
        result_df = pd.concat(all_data, ignore_index=True)
        
        # 컬럼 순서 재정렬
        columns_order = ['일자', '종목코드', '종목명', '시장', '시가', '고가', '저가', '종가', '거래량']
        # 존재하는 컬럼만 선택
        available_cols = [c for c in columns_order if c in result_df.columns]
        result_df = result_df[available_cols]
        
        return result_df
    else:
        return pd.DataFrame()


# 사용 예시
if __name__ == "__main__":
    # 최근 5일간의 데이터 수집
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
    
    print(f"데이터 수집 기간: {start_date} ~ {end_date}")
    
    # KOSPI + KOSDAQ 전체 데이터 수집
    # 테스트를 위해 종목 수를 제한하거나 특정 종목만 테스트하는 것이 좋을 수 있음
    # 여기서는 원래 로직대로 전체 실행 (시간이 오래 걸릴 수 있음)
    # df = get_all_market_data(start_date, end_date, market='ALL') # 전체 실행은 너무 오래 걸림

    # 빠른 테스트를 위해 KOSPI 상위 5개만 테스트하도록 코드 수정 제안 (User Request가 '실행시 오류'이므로 실행 가능하게 수정)
    # 하지만 원본 유지를 위해 'ALL'로 하되, 내부 루프에서 break를 걸거나 할 수는 없으니 
    # 일단 실행하여 에러가 나는지 확인.
    
    # NOTE: 전체 종목 수집은 시간이 매우 오래 걸리므로, 테스트 목적상 일부만 수행하도록 임시 수정 권장하나
    # 사용자 코드를 크게 바꾸지 않고 fix만 수행.
    df = get_all_market_data(start_date, end_date, market='ALL')
    
    print(f"\n총 수집된 데이터: {len(df):,}건")
    print("\n데이터 샘플:")
    print(df.head(10))
    
    if not df.empty:
        # CSV 파일로 저장
        filename = f"stock_data_{start_date}_{end_date}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n파일 저장 완료: {filename}")
        
        # 시장별 통계
        print("\n시장별 통계:")
        if '시장' in df.columns:
            print(df.groupby('시장')['종목코드'].nunique())
        
        # 일자별 데이터 건수
        print("\n일자별 데이터 건수:")
        if '일자' in df.columns:
            print(df.groupby('일자').size())
    else:
        print("\n수집된 데이터가 없습니다.")