import os

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
import sys
from collections import deque
import datetime
import time
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
    plain_number = text_edit.text().replace(",", "")

    try:
        # 정수로 변환하고 천 단위로 콤마를 추가
        formatted_number = f"{int(plain_number):,}"
    except ValueError:
        # 입력값이 없거나 숫자가 아닐 때
        formatted_number = ""

    # 커서 위치 저장
    cursor_pos = text_edit.cursorPosition()

    # 포맷된 텍스트 설정
    text_edit.setText(formatted_number)

    # 커서 위치 복원
    text_edit.setCursorPosition(cursor_pos)


class KiwoomAPI(QMainWindow):
    def __init__(
        self,
        tr_req_queue=None,
        tr_result_queue=None,
        order_tr_req_queue=None,
        websocket_req_queue=None,
        websocket_result_queue=None,
    ):
        super().__init__()

        # 현재 파일의 디렉토리를 기준으로 UI 파일 경로 설정
        ui_main_path = os.path.join(os.path.dirname(__file__), "main.ui")

        loader = QUiLoader()
        self.ui = loader.load(ui_main_path, None)
        self.resize(1050, 600)

        # 로드된 UI의 자식 위젯들을 이 윈도우로 옮기기
        self.setCentralWidget(self.ui)

        # UI의 모든 자식 위젯을 self의 속성으로 복사
        from PySide6.QtWidgets import QWidget

        for child in self.ui.findChildren(QWidget):
            if child.objectName():
                setattr(self, child.objectName(), child)

        self.show()

        self.autoOnPushButton.clicked.connect(self.auto_trade_on)
        self.autoOffPushButton.clicked.connect(self.auto_trade_off)

        # savePushButton이 존재하는지 확인 후 연결
        if hasattr(self, "savePushButton"):
            self.savePushButton.clicked.connect(self.save_settings)
        # buyAmountLineEdit이 존재하는지 확인 후 연결
        if hasattr(self, "buyAmountLineEdit"):
            self.buyAmountLineEdit.textChanged.connect(
                lambda: format_number(self.buyAmountLineEdit)
            )

        self.settings = QSettings("MyAPP20260125", "myApp20260125")

        # 아이콘 파일 경로 설정
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self.load_settings()

        self.tr_req_queue = tr_req_queue
        self.tr_result_queue = tr_result_queue
        self.order_tr_req_queue = order_tr_req_queue
        self.websocket_req_queue = websocket_req_queue
        self.websocket_result_queue = websocket_result_queue

        self.condition_df = pd.DataFrame(columns=["조건index", "조건명"])
        self.condition_name_to_index_dict = dict()
        self.condition_index_to_name_dict = dict()
        self.account_info_df = pd.DataFrame(
            columns=[
                "종목명",
                "현재가",
                "매입가",
                "보유수량",
                "매매가능수량",
                "수익률(%)",
            ]
        )

        # self.websocket_req_queue.put(
        #     {
        #         "action_id": "실시간등록",
        #         "종목코드": "005930",
        #     }
        # )

        self.websocket_req_queue.put(dict(action_id="조건검색식리스트"))
        self.tr_req_queue.put(dict(action_id="계좌조회"))

        self.timer1 = QTimer()
        self.timer1.timeout.connect(self.receive_websocket_result)
        self.timer1.start(10)  # 0.01초마다 실행

        self.timer2 = QTimer()
        self.timer2.timeout.connect(self.receive_tr_result)
        self.timer2.start(100)  # 0.1초마다 실행

    @log_exceptions
    def auto_trade_on(self):
        self.autoOnPushButton.setEnabled(False)
        self.autoOffPushButton.setEnabled(True)

        self.websocket_req_queue.put(
            dict(
                action_id="조건검색실시간등록",
                조건index=self.condition_name_to_index_dict[
                    self.buyConditionComboBox.currentText()
                ],
            )
        )
        logger.info(f"조건명: {self.buyConditionComboBox.currentText()} 실시간 등록")
        self.websocket_req_queue.put(
            dict(
                action_id="조건검색실시간등록",
                조건index=self.condition_name_to_index_dict[
                    self.sellConditionComboBox.currentText()
                ],
            )
        )
        logger.info(f"조건명: {self.sellConditionComboBox.currentText()} 실시간 등록")

    @log_exceptions
    def auto_trade_off(self):
        self.autoOnPushButton.setEnabled(True)
        self.autoOffPushButton.setEnabled(False)

        self.websocket_req_queue.put(
            dict(
                action_id="조건검색실시간해제",
                조건index=self.condition_name_to_index_dict[
                    self.buyConditionComboBox.currentText()
                ],
            )
        )
        logger.info(f"조건명: {self.buyConditionComboBox.currentText()} 실시간 해제")
        self.websocket_req_queue.put(
            dict(
                action_id="조건검색실시간해제",
                조건index=self.condition_name_to_index_dict[
                    self.sellConditionComboBox.currentText()
                ],
            )
        )
        logger.info(f"조건명: {self.sellConditionComboBox.currentText()} 실시간 해제")

    def receive_tr_result(self):
        self.timer2.stop()
        try:
            if not self.tr_result_queue.empty():
                data = self.tr_result_queue.get()
                if data.get("action_id") == "계좌조회":
                    account_info_dict = data["account_info_dict"]
                    logger.info(f"account_info_dict: {account_info_dict}")
                    self.account_info_df = data["df"][
                        [
                            "종목명",
                            "현재가",
                            "매입가",
                            "보유수량",
                            "매매가능수량",
                            "수익률(%)",
                        ]
                    ]
                    print(self.account_info_df)
                    ㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁㅁ 5편  14:20
                elif data.get("action_id") == "조건검색식리스트":
                    pass
                elif data.get("action_id") == "조건식실시간편입편출":
                    pass
        except Exception as e:
            logger.exception(e)
        self.timer2.start(100)

    def receive_websocket_result(self):
        self.timer1.stop()
        try:
            if not self.websocket_result_queue.empty():
                data = self.websocket_result_queue.get()
                if data.get("action_id") == "실시간체결":
                    print(data)
                elif data.get("action_id") == "조건검색식리스트":
                    self.condition_df = data["df"]
                    self.condition_name_to_index_dict = dict(
                        zip(self.condition_df["조건명"], self.condition_df["조건index"])
                    )
                    self.condition_index_to_name_dict = dict(
                        zip(self.condition_df["조건index"], self.condition_df["조건명"])
                    )
                    self.buyConditionComboBox.addItems(self.condition_df["조건명"])
                    self.sellConditionComboBox.addItems(self.condition_df["조건명"])
                    self.load_settings(is_init=False)
                    logger.info("조건검색식리스트 가져오기 성공!")
                elif data.get("action_id") == "조건식실시간편입편출":
                    조건식idx = data.get("조건식idx")
                    종목코드 = data.get("종목코드")
                    편입편출 = data.get("편입편출")
                    if (
                        self.condition_name_to_index_dict[
                            self.buyConditionComboBox.currentText()
                        ]
                        == 조건식idx
                        and 편입편출 == "I"
                    ):
                        logger.debug(f"종목코드: {종목코드} 매수 진행")

                    if all(
                        [
                            # TODOL 트래킹하는 자동매매 리스트에 있는 종목 이어야 함.
                            self.condition_name_to_index_dict[
                                self.sellConditionComboBox.currentText()
                            ]
                            == 조건식idx,
                            편입편출 == "I",
                        ]
                    ):
                        logger.debug(f"종목코드: {종목코드} 매도 진행")

        except Exception as e:
            logger.exception(e)
        self.timer1.start(10)

    @log_exceptions
    def load_settings(self, is_init=True):
        self.buyAmountLineEdit.setText(
            self.settings.value("buyAmountLineEdit", defaultValue="200,000", type=str)
        )
        self.marketBuyRadioButton.setChecked(
            self.settings.value("marketBuyRadioButton", defaultValue=True, type=bool)
        )
        self.limitBuyRadioButton.setChecked(
            self.settings.value("limitBuyRadioButton", defaultValue=False, type=bool)
        )
        self.marketSellRadioButton.setChecked(
            self.settings.value("marketSellRadioButton", defaultValue=True, type=bool)
        )
        self.limitSellRadioButton.setChecked(
            self.settings.value("limitSellRadioButton", defaultValue=False, type=bool)
        )
        self.stopLossCheckBox.setChecked(
            self.settings.value("stopLossCheckBox", defaultValue=True, type=bool)
        )
        self.trailingStopCheckBox.setChecked(
            self.settings.value("trailingStopCheckBox", defaultValue=True, type=bool)
        )
        self.limitBuySpinBox.setValue(
            self.settings.value("limitBuySpinBox", defaultValue=0, type=int)
        )
        self.amendOrderSpinBox.setValue(
            self.settings.value("amendOrderSpinBox", defaultValue=60, type=int)
        )
        self.stopLossDoubleSpinBox.setValue(
            self.settings.value("stopLossDoubleSpinBox", defaultValue=-2.00, type=float)
        )
        self.trailingStopDoubleSpinBox1.setValue(
            self.settings.value(
                "trailingStopDoubleSpinBox1", defaultValue=2.00, type=float
            )
        )
        self.trailingStopDoubleSpinBox2.setValue(
            self.settings.value(
                "trailingStopDoubleSpinBox2", defaultValue=-1.00, type=float
            )
        )
        self.limitSellSpinBox.setValue(
            self.settings.value("limitSellSpinBox", defaultValue=0, type=int)
        )

        if not is_init:
            self.buyConditionComboBox.setCurrentIndex(
                self.settings.value("buyConditionComboBox", 0, type=int)
            )
            self.sellConditionComboBox.setCurrentIndex(
                self.settings.value("sellConditionComboBox", 0, type=int)
            )

    @log_exceptions
    def save_settings(self):
        # Write window size and position to config file
        self.settings.setValue("buyAmountLineEdit", self.buyAmountLineEdit.text())
        self.settings.setValue(
            "buyConditionComboBox", self.buyConditionComboBox.currentIndex()
        )
        self.settings.setValue(
            "sellConditionComboBox", self.sellConditionComboBox.currentIndex()
        )
        self.settings.setValue(
            "marketBuyRadioButton", self.marketBuyRadioButton.isChecked()
        )
        self.settings.setValue(
            "limitBuyRadioButton", self.limitBuyRadioButton.isChecked()
        )
        self.settings.setValue(
            "marketSellRadioButton", self.marketSellRadioButton.isChecked()
        )
        self.settings.setValue(
            "limitSellRadioButton", self.limitSellRadioButton.isChecked()
        )
        self.settings.setValue("stopLossCheckBox", self.stopLossCheckBox.isChecked())
        self.settings.setValue(
            "trailingStopCheckBox", self.trailingStopCheckBox.isChecked()
        )
        self.settings.setValue("limitBuySpinBox", self.limitBuySpinBox.value())
        self.settings.setValue("amendOrderSpinBox", self.amendOrderSpinBox.value())
        self.settings.setValue(
            "stopLossDoubleSpinBox", self.stopLossDoubleSpinBox.value()
        )
        self.settings.setValue(
            "trailingStopDoubleSpinBox1", self.trailingStopDoubleSpinBox1.value()
        )
        self.settings.setValue(
            "trailingStopDoubleSpinBox2", self.trailingStopDoubleSpinBox2.value()
        )
        self.settings.setValue("limitSellSpinBox", self.limitSellSpinBox.value())


sys._excepthook = sys.excepthook


def my_exception_hook(exctype, value, traceback):
    # Print the error and traceback
    logger.debug(f"exctype: {exctype}, value: {value}, traceback: {traceback}")
    # Call the normal Exception hook after
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


# Set the exception hook to our wrapping function
sys.excepthook = my_exception_hook


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
        args=(order_tr_req_queue,),
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
