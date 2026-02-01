import time
import datetime
import functools
import inspect
from turtle import reset
import random
import requests

from loguru import logger
import pandas as pd

from config import api_key, api_secret_key, host


def log_exceptions(func):
    """함수 시그니처에 맞게 인자 자동 조정 + try-except 걸어주는 loguru용 데코레이터"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # 함수가 실제 몇 개 positional argument를 기대하는지 확인
            sig = inspect.signature(func)
            parameters = sig.parameters
            param_len = len(parameters)

            # self 빼고 나머지 인자 개수 확인
            if "self" in parameters:
                param_len -= 1

            # args를 필요한 만큼만 잘라서 함수 호출
            new_args = args[: param_len + 1]  # self + 필요한 만큼

            return func(*new_args, **kwargs)
        except Exception:
            logger.exception(f"Error occurred in {func.__qualname__}")

    return wrapper


class KiwoomTR:
    def __init__(self):
        self.token = self.login()

    @staticmethod
    def login():
        params = {
            "grant_type": "client_credentials",  # granttype
            "appkey": api_key,  # 앨키
            "secretkey": api_secret_key,  # 시크릿키
        }

        endpoint = "/oauth2/token"
        url = host + endpoint
        headers = {
            "Content-Type": "application/json;charset=UTF-8",  # 컨텐츠타입
        }
        response = requests.post(url, headers=headers, json=params)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러를 response 내용까지 추가해서 출력
            error_message = f"HTTP Error : {e}\nResponse Body : {response.text}"
            raise requests.HTTPError(error_message) from e

        token = response.json()["token"]
        logger.info("Success getting token!")
        return token

    # 종목정보 리스트
    @log_exceptions
    def fn_ka10099(self, data, cont_yn="N", next_key=""):
        # 1. 요청할 API URL
        endpoint = "/api/dostk/stkinfo"
        url = host + endpoint
        # 2. header 데이터
        headers = {
            "Content-Type": "application/json;charset=UTF-8",  # 컨텐츠타입
            "authorization": f"Bearer {self.token}",  # 접근토큰
            "cont-yn": cont_yn,  # 연속조회여부
            "next-key": next_key,  # 연속조회키
            "api-id": "ka10099",  # TR명
        }
        # 3. http POST 요청
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러를 response 내용까지 추가해서 출력
            error_message = f"HTTP Error : {e}\nResponse Body : {response.text}"
            raise requests.HTTPError(error_message) from e
        return response.json()["list"]

    # 일별주가요청
    @log_exceptions
    def fn_ka10086(self, data, cont_yn="N", next_key=""):
        # 1. 요청할 API URL
        endpoint = "/api/dostk/mrkcond"
        url = host + endpoint
        # 2. header 데이터
        headers = {
            "Content-Type": "application/json;charset=UTF-8",  # 컨텐츠타입
            "authorization": f"Bearer {self.token}",  # 접근토큰
            "cont-yn": cont_yn,  # 연속조회여부
            "next-key": next_key,  # 연속조회키
            "api-id": "ka10086",  # TR명
        }
        # 3. http POST 요청
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러를 response 내용까지 추가해서 출력
            error_message = f"HTTP Error : {e}\nResponse Body : {response.text}"
            raise requests.HTTPError(error_message) from e

        has_next = response.headers.get("cont-yn") == "Y"
        next_key = response.headers.get("next-key", "")

        res = response.json()["daly_stkpc"]
        df = pd.DataFrame(res)
        df = df[::-1].reset_index(drop=True)

        # 4. 응답 상태 코드와 데이터 출력
        for column_name in ["open_pric", "high_pric", "low_pric", "close_pric"]:
            df[column_name] = df[column_name].apply(lambda x: abs(int(x)))
        column_name_to_kor_name_map = {
            "date": "날짜",
            "open_pric": "시가",
            "high_pric": "고가",
            "low_pric": "저가",
            "close_pric": "종가",
            "pred_rt": "전일비",
            "flu_rt": "등락률",
            "trde_qty": "거래량",
            "amt_mn": "금액(백만)",
            "crd_rt": "신용비",
            "ind": "개인",
            "orgn": "기관",
            "for_qty": "외인수량",
            "frgn": "외국계",
            "prm": "프로그램",
            "for_rt": "외인비",
            "for_poss": "외인보유",
            "for_wght": "외인비중",
            "for_netprps": "외인순매수",
            "orgn_netprps": "기관순매수",
            "ind_netprps": "개인순매수",
            "crd_remn_rt": "신용잔고율",
        }

        df.rename(columns=column_name_to_kor_name_map, inplace=True)
        return df, has_next, next_key

    # 계좌평가잔고내역요청
    @log_exceptions
    def fn_kt00018(self, data, cont_yn="N", next_key=""):
        # 1. 요청할 API URL
        endpoint = "/api/dostk/acnt"
        url = host + endpoint
        # 2. header 데이터
        headers = {
            "Content-Type": "application/json;charset=UTF-8",  # 컨텐츠타입
            "authorization": f"Bearer {self.token}",  # 접근토큰
            "cont-yn": cont_yn,  # 연속조회여부
            "next-key": next_key,  # 연속조회키
            "api-id": "kt00018",  # TR명
        }
        # 3. http POST 요청
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러를 response 내용까지 추가해서 출력
            error_message = f"HTTP Error : {e}\nResponse Body : {response.text}"
            raise requests.HTTPError(error_message) from e

        res = response.json()
        has_next = response.headers.get("cont-yn") == "Y"
        next_key = response.headers.get("next-key", "")

        # 디버깅: API 응답 구조 확인
        print("=== API 응답 구조 확인 ===")
        print("응답 키들:", list(res.keys()))
        print("응답 내용:", res)
        print("=" * 50)

        # 안전한 계좌 정보 추출
        account_info_dict = dict(
            총매입금액=int(res.get("tot_pur_amt", 0)),
            총평가금액=int(res.get("tot_evlt_amt", 0)),
            총평가손익금액=int(res.get("tot_evlt_pl", 0)),
            총수익률=float(res.get("tot_prft_rt", 0.0)),
            추정예탁자산=int(res.get("prsm_dpst_aset_amt", 0)),
        )

        # 계좌 보유 종목 데이터 처리
        acnt_data = res.get("acnt_evlt_remn_indv_tot", [])

        if not acnt_data:
            # 보유 종목이 없는 경우 빈 DataFrame 반환
            print("보유 종목이 없습니다.")
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(acnt_data)
            print(f"보유 종목 수: {len(df)}")

            column_name_to_kor_name_map = {
                "stk_cd": "종목코드",
                "stk_nm": "종목명",
                "evltv_prft": "평가손익",
                "prft_rt": "수익률(%)",
                "pur_pric": "매입가",
                "pred_close_pric": "전일종가",
                "rmnd_qty": "보유수량",
                "trde_able_qty": "매매가능수량",
                "cur_prc": "현재가",
                "pred_buyq": "전일매수수량",
                "pred_sellq": "전일매도수량",
                "tdy_buyq": "금일매수수량",
                "tdy_sellq": "금일매도수량",
                "pur_amt": "매입금액",
                "pur_cmsn": "매입수수료",
                "evlt_amt": "평가금액",
                "sell_cmsn": "평가수수료",
                "tax": "세금",
                "sum_cmsn": "수수료합",
                "poss_rt": "보유비중(%)",
                "crd_tp": "신용구분",
                "crd_tp_nm": "신용구분명",
                "crd_loan_dt": "대출일",
            }

            # 컬럼명 변경
            df.rename(columns=column_name_to_kor_name_map, inplace=True)

            # 종목코드 컬럼이 존재하는 경우에만 처리
            if "종목코드" in df.columns:
                df["종목코드"] = df["종목코드"].apply(lambda x: x.replace("A", ""))

            # 숫자형 컬럼 변환
            for col in df.columns:
                if col != "종목코드":
                    df[col] = pd.to_numeric(df[col], errors="ignore")
        return account_info_dict, df, has_next, next_key

    @log_exceptions
    def request_all_acccount_info(self):
        # 계좌점보 연속 조회
        params = {
            "qry_tp": "1",  # 조회구분 1:합산, 2:개별
            "dmst_stex_tp": "KRX",  # 국내거래소구분 KRX: 한국거래소, NXT:넥스트트레이드
        }

        dfs = []
        next_key = ""
        has_next = False
        while True:
            time.sleep(1)
            account_info_dict, df, has_next, next_key = self.fn_kt00018(
                data=params,
                cont_yn="Y" if has_next else "N",
                next_key=next_key,
            )
            dfs.append(df)
            if not has_next:
                break

        all_df = pd.concat(dfs).reset_index(drop=True)
        all_df.reset_index(drop=True, inplace=True)
        return account_info_dict, all_df

    @log_exceptions
    def request_daily_chart_info(
        self,
        stock_code: "005930",
        start_date=datetime.datetime.now().strftime("%Y%m%d"),
        max_req_num=10,  # 최대 연속조회 요청 수
    ):
        pass

    # 시세표성정보요청
    @log_exceptions
    def fn_ka10007(self, data, cont_yn="N", next_key=""):
        endpoint = "/api/dostk/mrkcond"
        url = host + endpoint

        # 2. header 데이터
        headers = {
            "Content-Type": "application/json;charset=UTF-8",  # 컨텐츠타입
            "authorization": f"Bearer {self.token}",  # 접근토큰
            "cont-yn": cont_yn,  # 연속조회여부
            "next-key": next_key,  # 연속조회키
            "api-id": "ka10007",  # TR명
        }

        # 3. http POST 요청
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러를 response 내용까지 초가해서 출력
            error_message = f"HTTP Error: {e}\nResponse Body: {response.text}"
            raise requests.HTTPError(error_message) from e
        res = response.json()
        return dict(
            종목명=res["stk_nm"],
            상한가=abs(int(res["upl_pric"])),
            하한가=abs(int(res["lst_pric"])),
            현재가=abs(float(res["cur_prc"])),
        )

    # 주식 매수주문
    @log_exceptions
    def fn_kt10000(self, data, cont_yn="N", next_key=""):
        endpoint = "/api/dostk/ordr"
        url = host + endpoint

        # 2. header GIOIE
        headers = {
            "Content-Type": "application/json; charset=UTF-8",  # 컨텐츠타입
            "authorization": f"Bearer {self. token}",  # 접근토큰
            "cont-yn": cont_yn,  # 연속조회여부
            "next-key": next_key,  # 연속조회키
            "api-id": "kt10000",  # TR명
        }

        # 3. http POST 요청
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러를 response 내용까지 호가해서 출력
            error_message = f"HTTP Error: {e}\nResponse Body: {response.text}"
            raise requests.HTTPError(error_message) from e
        return response.json()["ord_no"]

    # 주식 매도주문
    @log_exceptions
    def fn_kt10001(self, data, cont_yn="N", next_key=""):
        endpoint = "/api/dostk/ordr"
        url = host + endpoint

        # 2. header GIOIE
        headers = {
            "Content-Type": "application/json; charset=UTF-8",  # 컨텐츠타입
            "authorization": f"Bearer {self. token}",  # 접근토큰
            "cont-yn": cont_yn,  # 연속조회여부
            "next-key": next_key,  # 연속조회키
            "api-id": "kt10001",  # TR명
        }

        # 3. http POST 요청
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러들 response 내용까지 추가해서 출력
            error_message = f"HTTP Error: {e}\nResponse Body: {response.text}"
            raise requests.HTTPError(error_message) from e

        return response.json()["ord_no"]

    # 주식 정정주문
    @log_exceptions
    def fn_kt10002(self, data, cont_yn="N", next_key=""):
        pass

    # 주식 취소주문
    @log_exceptions
    def fn_kt10003(self, data, cont_yn="N", next_key=""):
        pass

    # 전일대비등략률상위요청
    @log_exceptions
    def fn_ka10027(self, data, cont_yn="N", next_key=""):
        # 1. 키움증권 API 가이드에서 생플 함수 복사
        # 2. self, 변수 추가 / token 변수 지우기 / @log_exceptions 추가
        # 3. host 지우기
        # 4. response 부분 기호에 맞게 수정

        endpoint = "/api/dostk/rkinfo"
        url = host + endpoint

        # 2. header 데이터
        headers = {
            "Content-Type": "application/json; charset=UTF-8",  # 컨텐츠타입
            "authorization": f"Bearer {self.token}",  # 접근토큰
            "cont-yn": cont_yn,  # 연속조회여부
            "next-key": next_key,  # 연속조회키
            "api-id": "ka10027",  # TR명
        }

        # 3. http POST 요청
        response = requests.post(url, headers=headers, json=data)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # 에러들 response 내용까지 추가해서 출력
            error_message = f"HTTP Error: {e}\nResponse Body: {response.text}"
            raise requests.HTTPError(error_message) from e
        has_next = response.headers.get("cont-yn") == "Y"
        next_key = response.headers.get("next-key", "")

        res = response.json()
        df = pd.DataFrame(res["pred_pre_flu_rt_upper"])
        column_name_to_kor_name_map = {
            "stk_cls": "종목분류",
            "stk_cd": "종목코드",
            "stk_nm": "종목명",
            "cur_prc": "현재가",
            "pred_pre_sig": "전일대비기호",
            "pred_pre": "전일대비",
            "flu_rt": "등락률",
            "sel_req": "매도잔량",
            "buy_req": "매수잔량",
            "now_trde_qty": "현재거래량",
            "cntr_str": "체결강도",
            "cnt": "횟수",
        }

        # 컬럼명 변경
        df.rename(columns=column_name_to_kor_name_map, inplace=True)
        df["종목코드"] = df["종목코드"].apply(
            lambda x: x.replace("_AL", "").replace("A", "")
        )
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="ignore")
        return df, has_next, next_key

    def request_fluctuation_ranking(self, max_req_num=5):
        params = {
            "mrkt_tp": "000",  # 시작구분 - 000:전체, 001:코스피, 101:코스닥
            "sort_tp": "1",  # 정렬구분 - 1:상승률, 2:상승폭, 3:하락률, 4:하락폭
            "trde_qty_cnd": "0000",  # 거래량조건 - 0000:전체, 0010:만주이상, 0050:5만주이상, ...
            "stk_cnd": "0",  # 종목조건 - 0:전체, 1:관리종목제외, ...
            "crd_cnd": "0",  # 신용조건 - 0:전체조회, 1:신용융자A군, ...
            "updown_incls": "1",  # 상하한포함 - 0:불포함, 1:포함
            "pric_cnd": "0",  # 가격조건 - 0:전체, 1:1000원이만, ...
            "trde_prica_cnd": "0",  # 거래대금조건 - 0:전체, 3:3천만원이상, ...
            "stex_tp": "3",  # 거래소구분 - 1:KRX, 2:NXT, 3:통합
        }
        dfs = []
        next_key = ""
        has_next = False
        for _ in range(max_req_num):
            time.sleep(1)
            df, has_next, next_key = self.fn_ka10027(
                data=params,
                cont_yn="Y" if has_next else "N",
                next_key=next_key,
            )
            dfs.append(df)
            if not has_next:
                break
        all_df = pd.concat(dfs, ignore_index=True)
        return all_df


if __name__ == "__main__":
    kiwoom_tr = KiwoomTR()

    # # fn_ka10086 테스트 코드
    # params = {
    #     "stk_cd": "005930_AL",  # 종목코드 거래소별 종목코드(KRX:005930,NXT:005930_NX, SOR:005930_AL)
    #     "qry_dt": datetime.datetime.now().strftime("Y%m%d"),  # 조회일자 YYYYMMDD
    #     "indc_tp": "0",  # 표시구분 0:수량, 1:금액(백만원)
    # }

    # df, has_next, next_key = kiwoom_tr.fn_ka10086(data=params)
    # print(df.to_string())

    # # fn_ka10099 테스트 코드
    # params = {
    #     "mrkt_tp": "0"  # 0:코스피,10:코스닥,3:ELW,8:ETF,30:K-OTC,50:코넥스,5:신주인수권,4:뮤추얼펀드,6:리츠,9:하이일드
    # }
    # basic_info_dict = kiwoom_tr.fn_ka10099(params)
    # print(basic_info_dict)

    # # fn_ka10007 테스트 코드
    # params = {
    #     "stk_cd": "005930"  # 종목코드 거래소별 종목코드 (KRX:039490, NXT:039490_NX, SOR:039490_AL)
    # }
    # basic_info_dict = kiwoom_tr.fn_ka10007(params)
    # print(basic_info_dict)

    all_df = kiwoom_tr.request_fluctuation_ranking(max_req_num=3)
    print(all_df.to_string())
