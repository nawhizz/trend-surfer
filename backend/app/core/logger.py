"""
공통 로거 모듈

프로젝트 전체에서 일관된 로깅을 제공합니다.
- 콘솔 출력 (INFO 이상)
- 파일 출력 (DEBUG 이상, 일일 로테이션)
"""

import logging
import logging.handlers
import os
from datetime import datetime


# 로그 디렉토리 설정 (프로젝트 루트/logs)
_LOG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
)


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거 생성

    Args:
        name: 로거 이름 (보통 __name__ 사용)

    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger(name)

    # 이미 핸들러가 설정된 경우 중복 추가 방지
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 포맷터
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러 (INFO 이상)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 파일 핸들러 (DEBUG 이상, 일일 로테이션)
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        file_handler = logging.FileHandler(
            os.path.join(_LOG_DIR, f"trend_surfer_{today}.log"),
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # 파일 핸들러 생성 실패 시 콘솔만 사용
        logger.warning("로그 파일 생성 실패. 콘솔 로깅만 사용합니다.")

    return logger
