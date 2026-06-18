import subprocess
import sys
import os
import logging
import argparse
from datetime import datetime

# backend 경로 추가 (logger 사용을 위해)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.core.logger import get_logger

logger = get_logger("daily_routine")

# Script Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable

def _get_log_file_path() -> str | None:
    """현재 logger의 FileHandler 경로를 반환"""
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return handler.baseFilename
    return None


def run_script(script_name, args=[]):
    script_path = os.path.join(BASE_DIR, script_name)
    cmd = [PYTHON_EXE, script_path] + args

    logger.info(f"{'='*60}")
    logger.info(f"단계 시작: {script_name} {' '.join(args)}")
    logger.info(f"{'='*60}")

    # 서브프로세스에서 FileHandler를 쓰지 않도록 환경변수 설정
    # (daily_routine이 stdout을 직접 로그 파일에 기록해 순서 보장)
    env = {**os.environ, 'TREND_SURFER_SUBPROCESS': '1'}

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
        )

        log_path = _get_log_file_path()
        if log_path:
            with open(log_path, 'a', encoding='utf-8') as log_file:
                for line in process.stdout:
                    print(line, end='', flush=True)  # 즉시 stdout flush (순서 보장)
                    log_file.write(line)              # 로그 파일 직접 기록
                    log_file.flush()                  # 즉시 OS에 반영
        else:
            for line in process.stdout:
                print(line, end='', flush=True)

        process.wait()

        if process.returncode != 0:
            logger.error(f"{script_name} 실패 (exit code: {process.returncode})")
            return False

        logger.info(f"단계 완료: {script_name}")
        return True

    except FileNotFoundError:
        logger.error(f"스크립트 파일을 찾을 수 없음: {script_path}")
        return False
    except Exception as e:
        logger.error(f"{script_name} 실행 오류: {e}", exc_info=True)
        return False

def main():
    parser = argparse.ArgumentParser(description="Trend Surfer Daily Routine")
    parser.add_argument("--date", help="Target Date YYYY-MM-DD (default: today)")
    parser.add_argument("--skip_tickers", action="store_true", help="Skip ticker update step")
    parser.add_argument("--skip_adjust", action="store_true", help="Skip adjustment check step")
    
    args = parser.parse_args()
    
    from datetime import timedelta
    target_date = args.date if args.date else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"일일 루틴 시작: {target_date}")
    
    # 1. 종목 마스터 갱신
    if not args.skip_tickers:
        if not run_script("run_collector.py", ["--mode", "tickers"]):
            logger.error("루틴 중단: 단계 1 (종목 마스터 갱신)")
            sys.exit(1)

    # 2. 수정주가 확인 및 재계산
    if not args.skip_adjust:
        if not run_script("update_adjusted_prices.py", ["--date", target_date, "--start_date", "2020-01-01"]):
            logger.error("루틴 중단: 단계 2 (수정주가 업데이트)")
            sys.exit(1)

    # 3. 당일 시세 수집
    if not run_script("run_collector.py", ["--mode", "daily", "--date", target_date]):
        logger.error("루틴 중단: 단계 3 (당일 시세 수집)")
        sys.exit(1)

    # 4. 기술적 지표 계산
    if not run_script("run_daily_indicators.py", ["--date", target_date]):
        logger.error("루틴 중단: 단계 4 (지표 계산)")
        sys.exit(1)

    # 5. 경고종목 업데이트 (실패해도 계속 진행)
    if not run_script("update_warning_stocks.py"):
        logger.warning("단계 5 (경고종목 업데이트) 실패, 계속 진행")

    # 6. 전략 신호 스캔
    if not run_script("run_strategy.py", ["--date", target_date]):
        logger.error("루틴 중단: 단계 6 (전략 신호 스캔)")
        sys.exit(1)

    logger.info(f"{'='*60}")
    logger.info("일일 루틴 완료")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    main()
