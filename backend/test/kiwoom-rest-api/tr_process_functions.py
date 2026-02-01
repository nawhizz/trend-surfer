import time
from multiprocessing import Queue
from loguru import logger

from utils import KiwoomTR


def tr_general_req_func(tr_req_in_queue: Queue, tr_req_out_queue: Queue):
    time.sleep(1.0)  # 토큰 요청 분산을 위한 딜레이
    logger.debug(f"tr_general_req_func start!")
    kiwoom_tr = KiwoomTR()
    while True:
        data = tr_req_in_queue.get()
        logger.info(f"TR 일반 요청: {data}")
        if data["action_id"] == "계좌조회":
            account_info_dict, df = kiwoom_tr.request_all_account_info()
            tr_req_out_queue.put(
                dict(
                    action_id="계좌조회",
                    df=df,
                    account_info_dict=account_info_dict,
                )
            )
        elif data["action_id"] == "~~~~":
            tr_req_out_queue.put(
                dict(
                    action_id=data["action_id"],
                )
            )


def tr_order_req_func(tr_order_req_in_queue: Queue):
    time.sleep(3.0)  # 토큰 요청 분산을 위한 딜레이
    logger.debug(f"tr_order_req_func start!")
    kiwoom_tr = KiwoomTR()
    while True:
        data = tr_order_req_in_queue.get()
        if data["action_id"] == "~~":
            pass
        elif data["action_id"] == "~~~~":
            pass
