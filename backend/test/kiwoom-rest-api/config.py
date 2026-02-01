is_paper_trading = True  # 모의투자 여부 : False 또는 True
api_key = "2YPjr6p-flZI2z-wBLqup5wS7bablu0VWu6sfmQDmMI"  # API KEY
api_secret_key = "KCePQBc_AaTE6Ul8fxyjvTKLa11S_JW4Ku1NWCgYcl8"  # API SECRET KEY

host = "https://mockapi.kiwoom.com" if is_paper_trading else "https://api.kiwoom.com"
websocket_url = (
    "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
    if is_paper_trading
    else "wss://api.kiwoom.com:10000/api/dostk/websocket"
)
