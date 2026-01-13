import requests
import json

API_BASE = "https://data-dbg.krx.co.kr/svc/apis/sto"
AUTH_KEY = "537250F73A504836870208F5AA4F0A8BE512891F"

headers = {"AUTH_KEY": AUTH_KEY, "Content-Type": "application/json", "Accept": "application/json"}

def probe_simple():
    url = f"{API_BASE}/stk_bydd_trd"
    payload = {"basDd": "20240103"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        data = r.json()
        item = data['OutBlock_1'][0]
        # Print Keys only first
        print("Keys:", item.keys())
        # Print CMPPREVDD_PRC specifically
        if 'CMPPREVDD_PRC' in item:
            print(f"CMPPREVDD_PRC: {item['CMPPREVDD_PRC']}")
        if 'FLUC_RT' in item:
            print(f"FLUC_RT: {item['FLUC_RT']}")
        if 'TDD_CLSPRC' in item:
             print(f"TDD_CLSPRC: {item['TDD_CLSPRC']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    probe_simple()
