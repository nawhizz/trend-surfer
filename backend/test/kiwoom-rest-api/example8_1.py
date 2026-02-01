import os

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
import sys
import datetime
from multiprocessing import Process, Queue

from loguru import logger
import pandas as pd
from PySide6.QtCore import Qt, QSettings, QTimer, QAbstractTableModel, QTime
from PySide6 import QtGui
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtUiTools import QUiLoader

from tr_process_functions import tr_general_req_func, tr_order_req_func
from websocket_functions import run_websocket
from utils import log_exceptions

# 현재 파일의 디렉토리를 기준으로 UI 파일 경로 설정
ui_main_path = os.path.join(os.path.dirname(__file__), "main.ui")

loader = QUiLoader()

form_class = loader.load(ui_main_path, None)


class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return str(self._data.iloc[index.row(), index.column()])
            elif role == Qt.TextAlignmentRole:
                return Qt.AlignCenter
            if role == Qt.ForegroundRole:
                if self._data.columns[index.column()] in ("수익률(%)", "전일대비(%)"):
                    try:
                        value = self._data.iloc[index.row(), index.column()]
                        if isinstance(value, str) and "," in value:
                            value = int(value.replace(",", ""))
                        if float(value) < 0:
                            return QColor(Qt.blue)
                        elif float(value) > 0:
                            return QColor(Qt.red)
                    except:
                        return str(value)
        return None

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._data.columns[section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return self._data.index[section]
        return None

    def setData(self, index, value, role):
        return False

    def flags(self, index):
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable


def format_number(text_edit):
    # 숫자만 추출 (콤마 제거)
    plain_number = text_edit.text().replace(" , ", "")

    try:
        # 정수로 변환하고 천 단위로 콤마를 추가
        formatted_number = f"{int(plain_number):,}"
    except ValueError:
        # 입력값이 없거나 숫자가 아닐 때
        formatted_number = 1

    # 커서 위치 저장
    cursor_pos = text_edit.cursorPosition()

    # 포맷된 텍스트 설정
    text_edit.setText(formatted_number)

    # 커서 위치 복원
    text_edit.setCursorPosition(cursor_pos)


class KiwoomAPI(QMainWindow, form_class):
    def __init__(
        self,
        tr_req_queue=None,
        tr_result_queue=None,
        order_tr_req_queue=None,
        websocket_req_queue=None,
        websocket_result_queue=None,
    ):

        super().__init__()
        self.setupUi(self)
        self.show()
        # self.autoOnPushButton.clicked.connect(self.auto_trade_on)
        # self.auto0ffPushButton.clicked.connect(self.auto_trade_off)
        # self.savePushButton.clicked.connect(self.save_settings)
        # self.popPushButton.clicked.connect(selfIpop_btn_clicked)
        self.buyAmountLineEdit.textChanged.connect(
            lambda: format_number(self.buyAmountLineEdit)
        )
        self.settings = QSettings("MyAPP20260125", "myApp20260125")
        self.setWindowIcon(QtGui.QIcon("icon.ico"))
        self.load_settings()

        # self.tr_req_queue = tr_req_queue
        # self.tr_result_queue = tr_result_queue
        # self.order_tr_req_queue = order_tr_req_queue
        # self.websocket_req_queue = websocket_req_queue
        # self.websocket_result_queue = websocket_result_queue

        # self.condition_df = pd.DataFrame(columns=["조건index", "조건명"])
        # self.condition_name_to_index_dict = dict()
        # self.condition_index_to_name_dict = dict()
        # self.account_info_df = pd.DataFrame(
        #     columns=[
        #         "종목명",
        #         "현재가",
        #         "매입가",
        #         "보유수량",
        #         "매매가능수량",
        #         "수익률(%)",
        #     ]
        # )
        # try:
        #     self.realtime_tracking_df = pd.read_pickle("realtime_tracking_df.pkl")
        # except FileNotFoundError:
        #     self.realtime_tracking_df = pd.DataFrame(
        #         columns=[
        #             "종목명",
        #             "현재가",
        #             "매입가",
        #             "수익률(%)",
        #             "트레일링 발동 여부",
        #             "트레일링 발동 후 고가",
        #             "매수주문여부",
        #             "매도주문여부",
        #         ]
        #     )
        # self.last_saved_realtime_tracking_df = self.realtime_tracking_df.copy(deep=True)
        # self.stock_code_to_basic_info_dict = dict()
        # self.order_info_df = pd.DataFrame(
        #     columns=["주문접수시간", "종목코드", "주문수량", "매도주문여부"]
        # )
        # self.realtime_registered_codes_set = set()
        # self.amend_ordered_num_set = set()

        # self.transaction_cost = 0.18  # % 단위, 세금: 0.15% + 수수료 0.015% × 2
        # self.current_realtime_count = 0
        # self.max_realtime_count = 95
        # self.is_no_transaction = True
        # self.has_init = False
        # self.init_time()


if __name__ == "__main__":
    tr_req_queue = Queue()
    tr_result_queue = Queue()
    order_tr_req_queue = Queue()
    websocket_req_queue = Queue()
    websocket_result_queue = Queue()
    tr_gen_process = Process(
        target=tr_general_req_func,
        args=(tr_req_queue, tr_result_queue),
        daemon=True,
    )
    tr_order_process = Process(
        target=tr_order_req_func,
        args=(order_tr_req_queve,),
        daemon=True,
    )
    tr_websocket_process = Process(
        target=run_websocket,
        args=(websocket_req_queue, websocket_result_queue),
        daemon=True,
    )
    tr_gen_process.start()
    tr_order_process.start()
    tr_websocket_process.start()

    app = QApplication(sys.argv)
    kiwoom_api = KiwoomAPI(
        tr_req_queue=tr_req_queue,
        tr_result_queue=tr_result_queue,
        order_tr_req_queue=order_tr_req_queue,
        websocket_req_queue=websocket_req_queue,
        websocket_result_queue=websocket_result_queue,
    )

    sys.exit(app.exec())
