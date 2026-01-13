import requests
import os
import json

# Use the working endpoint and key
API_BASE = "https://data-dbg.krx.co.kr/svc/apis/sto"
AUTH_KEY = "537250F73A504836870208F5AA4F0A8BE512891F"

headers = {
    "AUTH_KEY": AUTH_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def probe_fields():
    print("--- Probing Market Daily Trade (For Fields) ---")
    url = f"{API_BASE}/stk_bydd_trd"
    # Jan 3 2024
    payload = {"basDd": "20240103"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        data = r.json()
        item = data['OutBlock_1'][0]
        print("First Item Fields:")
        print(json.dumps(item, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

def probe_single_ticker_history():
    print("\n--- Probing Single Ticker History Endpoint Candidates ---")
    # Guessing endpoints based on common naming: stk_isu_bydd_trd (Stock Item By Date Trade)
    candidates = [
        "/stk_isu_bydd_trd", 
        "/stk_bydd_trd_isu",
        "/isu_bydd_trd"
    ]
    
    # Payload for single ticker history usually needs Start/End date and Code
    params = {
        "strtDd": "20240101",
        "endDd": "20240105",
        "isuCd": "KR7005930003" # Samsung Elec ISIN (or short code?)
    }
    
    for ep in candidates:
        url = f"{API_BASE}{ep}"
        print(f"Testing {url}...")
        try:
            r = requests.post(url, headers=headers, json=params, timeout=5)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                print("Response Snippet:", r.text[:200])
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    probe_fields()
    probe_single_ticker_history()
