"""
시장경보 종목 업데이트 스크립트

키움증권 REST API (ka10099)를 사용하여 종목별 경고 정보를 조회하고
stocks 테이블의 warning_type 필드를 업데이트합니다.

ka10099 응답 필드:
- auditInfo: 감리정보 (정상, 투자주의환기종목 등)
- state: 상태 (관리종목, 증거금100% 등)
- orderWarning: 주문경고 (0, 1 등)

warning_type 매핑:
- NULL: 정상
- CAUTION: 투자주의환기종목 (auditInfo)
- ADMIN: 관리종목 (state)
- DELISTING: 정리매매 (state)
- HALT: 거래정지 (state)
- WARNING: 투자경고 (state)
"""

import sys
import os
import requests
import time

# backend 모듈 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.db.client import supabase
from app.core.logger import get_logger
from dotenv import load_dotenv

logger = get_logger("update_warning_stocks")

# .env 파일 로드
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

# 키움증권 REST API 설정
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY", "").strip('"')
KIWOOM_APP_SECRET = os.getenv("KIWOOM_APP_SECRET", "").strip('"')
KIWOOM_IS_PAPER = os.getenv("KIWOOM_IS_PAPER_TRADING", "True").lower() == "true"

# API 기본 URL (키움증권 REST API)
KIWOOM_HOST = "https://mockapi.kiwoom.com" if KIWOOM_IS_PAPER else "https://api.kiwoom.com"

# 경고 키워드 매핑
AUDIT_INFO_MAP = {
    "투자주의환기종목": "CAUTION",
    "투자주의": "CAUTION",
}

STATE_MAP = {
    "관리종목": "ADMIN",
    "정리매매": "DELISTING",
    "거래정지": "HALT",
    "투자경고": "WARNING",
    "투자위험": "RISK",
    "단기과열": "OVERHEAT",
}


def get_access_token() -> str | None:
    """
    키움증권 REST API 접근 토큰을 발급받습니다.
    """
    url = f"{KIWOOM_HOST}/oauth2/token"
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    body = {
        "grant_type": "client_credentials",
        "appkey": KIWOOM_APP_KEY,
        "secretkey": KIWOOM_APP_SECRET,
    }
    
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("token")
        if token:
            logger.info("액세스 토큰 발급 완료")
            return token
        else:
            logger.error(f"토큰 없음: {data}")
            return None
    except requests.HTTPError as e:
        logger.error(f"토큰 발급 HTTP 오류: {e} / {resp.text}")
        return None
    except Exception as e:
        logger.error(f"토큰 발급 오류: {e}")
        return None


def fetch_stock_list(access_token: str, market_type: str) -> list[dict] | None:
    """
    특정 시장의 전체 종목 목록과 경고 정보를 조회합니다.
    
    Args:
        access_token: 접근 토큰
        market_type: 시장 구분
            - "0": 코스피
            - "10": 코스닥
            
    Returns:
        종목 정보 딕셔너리 리스트
    """
    url = f"{KIWOOM_HOST}/api/dostk/stkinfo"
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "authorization": f"Bearer {access_token}",
        "cont-yn": "N",
        "next-key": "",
        "api-id": "ka10099",
    }
    
    body = {
        "mrkt_tp": market_type
    }
    
    all_stocks = []
    next_key = ""
    cont_yn = "N"
    
    # 연속 조회
    while True:
        headers["cont-yn"] = cont_yn
        headers["next-key"] = next_key
        
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            stock_list = data.get("list", [])
            all_stocks.extend(stock_list)
            
            # 연속조회 확인
            has_next = resp.headers.get("cont-yn") == "Y"
            next_key = resp.headers.get("next-key", "")
            
            if not has_next:
                break
            
            cont_yn = "Y"
            time.sleep(0.5)  # API 호출 제한 방지
            
        except requests.HTTPError as e:
            logger.error(f"시장 {market_type} 종목 조회 HTTP 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"시장 {market_type} 종목 조회 오류: {e}")
            return None
    
    return all_stocks


def determine_warning_type(stock_info: dict) -> str | None:
    """
    종목 정보에서 warning_type을 결정합니다.
    
    Args:
        stock_info: ka10099 응답의 종목 정보 딕셔너리
        
    Returns:
        warning_type 값 (NULL이면 None)
    """
    audit_info = stock_info.get("auditInfo", "")
    state = stock_info.get("state", "")
    
    # 1. state에서 경고 유형 확인 (더 심각한 상태)
    for keyword, warning_type in STATE_MAP.items():
        if keyword in state:
            return warning_type
    
    # 2. auditInfo에서 경고 유형 확인
    for keyword, warning_type in AUDIT_INFO_MAP.items():
        if keyword in audit_info:
            return warning_type
    
    # 3. 정상
    return None


def update_warning_stocks():
    """
    키움증권 API를 사용하여 경고 종목 정보를 업데이트합니다.
    """
    logger.info("경고종목 업데이트 시작 (키움 REST API)")

    # 1. 접근 토큰 발급
    access_token = get_access_token()
    if not access_token:
        logger.error("액세스 토큰 발급 실패. 종료.")
        return

    # 2. KOSPI/KOSDAQ 종목 목록 조회 — 하나라도 실패 시 DB 리셋하지 않음
    warning_stocks = {}  # {ticker: warning_type}
    fetch_failed = False

    for market_type, market_name in [("0", "KOSPI"), ("10", "KOSDAQ")]:
        logger.info(f"{market_name} 종목 조회 중...")
        stocks = fetch_stock_list(access_token, market_type)
        if stocks is None:
            logger.error(f"{market_name} 조회 실패 — DB 업데이트를 중단합니다.")
            fetch_failed = True
            break
        logger.info(f"{market_name} {len(stocks)}건 조회 완료")

        for stock in stocks:
            code = stock.get("code", "")
            warning_type = determine_warning_type(stock)
            if code and warning_type:
                warning_stocks[code] = warning_type

        time.sleep(1)  # 시장 간 API 호출 간격

    if fetch_failed:
        return

    logger.info(f"경고 종목 {len(warning_stocks)}건 감지")

    # 3. DB 업데이트 — 양쪽 시장 조회 성공 시에만 리셋
    try:
        supabase.table("stocks").update({"warning_type": None}).neq("ticker", "").execute()
    except Exception as e:
        logger.error(f"warning_type 초기화 오류: {e}")
        return

    # 4. 경고 종목 업데이트
    warning_counts = {}
    for ticker, warning_type in warning_stocks.items():
        try:
            supabase.table("stocks").update({"warning_type": warning_type}).eq("ticker", ticker).execute()
            warning_counts[warning_type] = warning_counts.get(warning_type, 0) + 1
        except Exception as e:
            logger.error(f"{ticker} 업데이트 오류: {e}")

    for wtype, count in sorted(warning_counts.items()):
        logger.info(f"  {wtype}: {count}건")

    logger.info("경고종목 업데이트 완료")


def main():
    """
    메인 함수
    """
    update_warning_stocks()


if __name__ == "__main__":
    main()
