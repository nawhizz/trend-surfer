import requests
import os
import json

API_BASE = "https://data-dbg.krx.co.kr/svc/apis/sto"
AUTH_KEY = "537250F73A504836870208F5AA4F0A8BE512891F"

headers = {"AUTH_KEY": AUTH_KEY, "Content-Type": "application/json", "Accept": "application/json"}

def probe_counts():
    date = "20240103"
    print(f"--- Probing Counts for {date} ---")
    
    # KOSPI
    url = f"{API_BASE}/stk_bydd_trd"
    payload = {"basDd": date}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        data = r.json()
        rows = data.get("OutBlock_1", [])
        print(f"KOSPI Rows: {len(rows)}")
        if rows:
            print(f"Sample KOSPI Ticker Keys: {list(rows[0].keys())}")
            print(f"Sample KOSPI Item: ISU_SRT_CD={rows[0].get('ISU_SRT_CD')}, ISU_CD={rows[0].get('ISU_CD')}")
    except Exception as e:
        print(f"KOSPI Error: {e}")

    # KOSDAQ
    url = f"{API_BASE}/ksq_bydd_trd"
    payload = {"basDd": date}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        data = r.json()
        rows = data.get("OutBlock_1", [])
        print(f"KOSDAQ Rows: {len(rows)}")
        if rows:
            print(f"Sample KOSDAQ Ticker Keys: {list(rows[0].keys())}")
            print(f"Sample KOSDAQ Item: ISU_SRT_CD={rows[0].get('ISU_SRT_CD')}, ISU_CD={rows[0].get('ISU_CD')}")
    except Exception as e:
        print(f"KOSDAQ Error: {e}")

if __name__ == "__main__":
    probe_counts()
