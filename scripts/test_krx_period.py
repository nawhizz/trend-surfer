import requests
import os
from dotenv import load_dotenv
import pprint

# Load env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

api_key = os.getenv("KRX_API_KEY")
base_url = "https://data-dbg.krx.co.kr/svc/apis/sto"
headers = {
    "AUTH_KEY": api_key,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def test_ticker_period():
    endpoint = "/stk_bydd_trd" # 주식 > 종목시세 > 개별종목 시세 추이
    url = base_url + endpoint
    
    # 삼성전자 (005930) Full Code: KR7005930003
    payload = {
        "isuCd": "KR7005930003", 
        "strtDd": "20240101",
        "endDd": "20240105"
    }
    
    print(f"Testing {url} with payload {payload}")
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # print first block
            if "OutBlock_1" in data:
                print(f"Count: {len(data['OutBlock_1'])}")
                if len(data['OutBlock_1']) > 0:
                    pprint.pprint(data['OutBlock_1'][0])
            else:
                print("No OutBlock_1 found. Response keys:", data.keys())
                pprint.pprint(data)
        else:
            print(resp.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ticker_period()
