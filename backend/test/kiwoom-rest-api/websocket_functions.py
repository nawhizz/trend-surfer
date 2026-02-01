import time
import asyncio
import websockets
import json
from multiprocessing import Queue

from loguru import logger
import pandas as pd

from utils import KiwoomTR
from config import websocket_url


class WebSocketClient:
    def __init__(self, uri="", req_in_queue=None, realtime_out_queue=None):
        self.uri = uri
        self.websocket = None
        self.connected = False
        self.keep_running = True
        time.sleep(2.0)  # 토큰 요청 분산을 위한 딜레이
        kiwoom_tr = KiwoomTR()
        self.token = kiwoom_tr.token
        self.req_in_queue = req_in_queue
        self.realtime_out_queue = realtime_out_queue
        self.stock_code_to_group_num_dict = dict()
        self.group_num = 10

    # WebSocket 서버에 연결합니다.
    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            self.connected = True
            logger.info("서버와 연결을 시도 중입니다.")

            # 로그인 패킷
            param = {"trnm": "LOGIN", "token": self.token}

            logger.info("실시간 시세 서버로 로그인 패킷을 전송합니다.")
            # 웹소켓 연결 시 로그인 정보 전달
            await self.send_message(message=param)

        except Exception as e:
            logger.info(f"Connection error: {e}")
            self.connected = False

    # 서버에 메시지를 보냅니다. 연결이 없다면 자동으로 연결합니다.
    async def send_message(self, message):
        if not self.connected:
            await self.connect()  # 연결이 끊어졌다면 재연결

        # 연결 상태와 websocket 객체 확인
        if not self.connected or self.websocket is None:
            logger.error("WebSocket 연결이 없습니다. 메시지를 보낼 수 없습니다.")
            return False

        try:
            # message가 문자열이 아니면 JSON으로 직렬화
            if not isinstance(message, str):
                message = json.dumps(message)

            await self.websocket.send(message)
            logger.info(f"Message sent: {message}")
            return True
        except Exception as e:
            logger.error(f"메시지 전송 실패: {e}")
            self.connected = False
            return False

    async def get_group_num(self):
        self.group_num += 1
        return self.group_num

    async def req_condition_name_list(self):
        logger.info("조건검색식 리스트 요청!")
        await self.send_message(
            {
                "trnm": "CNSRLST",  # TR명
            }
        )

    # 서버에서 오는 메시지를 수신하여 출력합니다.
    async def receive_messages(self):
        while self.keep_running:
            try:
                # websocket 연결 확인
                if not self.connected or self.websocket is None:
                    logger.error("WebSocket 연결이 없습니다. 수신을 중단합니다.")
                    break

                # 서버로부터 수신한 메시지를 JSON 형식으로 파싱
                if not self.req_in_queue.empty():
                    req_data = self.req_in_queue.get()
                    if req_data["action_id"] == "실시간등록":
                        stock_code = req_data["종목코드"]
                        await self.register_realtime_group(stock_code)
                    elif req_data["action_id"] == "실시간해제":
                        종목코드 = req_data["종목코드"]
                        group_num = self.stock_code_to_group_num_dict.get(
                            종목코드, None
                        )
                        if group_num:
                            await self.remove_realtime_group(group_num=group_num)
                    elif req_data["action_id"] == "조건검색식리스트":
                        await self.req_condition_name_list()
                    elif req_data["action_id"] == "조건검색실시간등록":
                        await self.register_condition_realtime_result(
                            req_data["조건index"]
                        )
                    elif req_data["action_id"] == "조건검색실시간해제":
                        await self.remove_condition_realtime(req_data["조건index"])

                response = json.loads(await self.websocket.recv())
                tr_name = response.get("trnm")
                # logger.info(f'tr_name : {tr_name}')

                # 메시지 유형이 LOGIN일 경우 로그인 시도 결과 체크
                if tr_name == "LOGIN":
                    if response.get("return_code") != 0:
                        logger.info(
                            "로그인 실패하였습니다. : ", response.get("return_msg")
                        )
                        await self.disconnect()
                    else:
                        logger.info("로그인 성공하였습니다.")
                # 메시지 유형이 PING일 경우 수신값 그대로 송신
                elif tr_name == "PING":
                    await self.send_message(response)
                # 조건검색식 리스트 수신
                elif tr_name == "CNSRLST":  # 조건검색식 리스트 수신
                    df = pd.DataFrame(columns=["조건index", "조건명"])
                    for condition_idx, condition_name in response.get("data", []):
                        df.loc[len(df)] = {
                            "조건index": condition_idx,
                            "조건명": condition_name,
                        }
                    self.realtime_out_queue.put(
                        dict(action_id="조건검색식리스트", df=df)
                    )
                # 조건검색 요청 일반 결과 수신
                elif tr_name == "CNSRREQ":
                    logger.info(f"결과: {response}")
                    stock_code_list = []
                    for per_stock_info_map in response.get("data", []):
                        종목코드 = (
                            per_stock_info_map["jmcode"]
                            .replace("_AL", "")
                            .replace("A", "")
                        )
                        stock_code_list.append(종목코드)
                    logger.info(f"종목코드 리스트: {stock_code_list}")
                # 메시지 유형이 REAL일 경우 실시간 체결과 호가 수신
                elif tr_name == "REAL":
                    for chunk_data_info_map in response.get("data", []):
                        if (
                            chunk_data_info_map["name"] == "조건검색"
                        ):  # 'name' 또는 'type'으로 구분하여 접근
                            info_map = chunk_data_info_map["values"]
                            조건식idx = info_map["841"].split(" ")[0]
                            종목코드 = (
                                info_map["9001"].replace("_AL", "").replace("A", "")
                            )
                            편입편출 = info_map["843"]  # "I": 편입, "D": 편출
                            logger.info(
                                f"종목코드: {종목코드}, " f"편입편출: {편입편출}"
                            )
                            self.realtime_out_queue.put(
                                dict(
                                    action_id="조건식실시간편입편출",
                                    조건식index=조건식idx,
                                    종목코드=종목코드,
                                    편입편출=편입편출,
                                )
                            )
                else:
                    logger.info(f"실시간 시세 서버 응답 수신: {response}")

            except websockets.ConnectionClosed:
                logger.info("Connection closed by the server")
                self.connected = False
                await self.websocket.close()

    async def register_condition_realtime_result(self, condition_idx):
        logger.info(f"{condition_idx} 실시간 등록")
        await self.send_message(
            {
                "trnm": "CNSRREQ",  # 서비스명
                "seq": f"{condition_idx}",  # 조건검색식 일련번호
                "search_type": "1",  # 조회타입 (1: 실시간간)
                "stex_tp": "K",  # 거래소구분
            }
        )

    async def remove_condition_realtime(self, condition_idx):
        logger.info(f"{condition_idx} 실시간 등록 해제")
        await self.send_message(
            {
                "trnm": "CNSRCLR",  # 서비스명
                "seq": f"{condition_idx}",  # 조건검색식 일련번호
            }
        )

    async def register_realtime_group(self, stock_code):
        self.stock_code_to_group_num_dict[stock_code] = await self.get_group_num()
        await self.send_message(
            {
                "trnm": "REG",  # 서비스명 (REG: 등록, REMOVE: 해제)
                "grp_no": f"{self.group_num}",  # 그룹번호
                "refresh": "0",  # 기존등록유지여부 (1: 유지, 0: 삭제후등록)
                "data": [
                    {  # 실시간 등록 리스트
                        "item": [
                            f"{stock_code}_AL"
                        ],  # 실시간 등록 요소 (SOR 시세 등록)
                        "type": ["0B"],  # 실시간 항목 (주식 체결)
                    }
                ],
            }
        )
        logger.info(f"종목코드: {stock_code} 등록 완료!")

    async def remove_realtime_group(self, group_num="1"):
        logger.info(f"그룹번호: {group_num} 실시간 등록 해지!")
        await self.send_message(
            {
                "trnm": "REMOVE",  # 서비스명
                "grp_no": group_num,  # 그룹번호
            }
        )

    # WebSocket 실행
    async def run(self):
        await self.connect()
        await self.receive_messages()

    # WebSocket 연결 종료
    async def disconnect(self):
        self.keep_running = False
        if self.connected and self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("Disconnected from WebSocket server")


async def main(req_in_queue, realtime_out_queue):
    # WebSocketClient 전역 변수 선언
    websocket_client = WebSocketClient(websocket_url, req_in_queue, realtime_out_queue)

    # WebSocket 클라이언트를 백그라운드에서 실행합니다.
    receive_task = asyncio.create_task(websocket_client.run())

    # 연결 대기 (최대 5초)
    await asyncio.sleep(2)

    # 연결 상태 확인
    if not websocket_client.connected or websocket_client.websocket is None:
        logger.error("WebSocket 연결 실패. 프로그램을 종료합니다.")
        websocket_client.keep_running = False
        receive_task.cancel()
        return

    logger.info("WebSocket 연결 성공. 실시간 등록을 시작합니다.")

    # 수신 작업이 종료될 때까지 대기
    try:
        await receive_task
    except asyncio.CancelledError:
        logger.info("수신 작업이 취소되었습니다.")
    finally:
        await websocket_client.disconnect()


def run_websocket(req_in_queue: Queue, realtime_out_queue: Queue):
    time.sleep(1.5)
    asyncio.run(main(req_in_queue, realtime_out_queue))


# asyncio로 프로그램을 실행합니다.
if __name__ == "__main__":
    req_in_queue = Queue()
    realtime_out_queue = Queue()
    req_in_queue.put(
        {
            "action_id": "실시간등록",
            "종목코드": "005930",
        }
    )
    run_websocket(req_in_queue, realtime_out_queue)
