import argparse
import sys
import os
from datetime import datetime
import pandas as pd

# Add projects root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app.services.strategy_scanner import strategy_scanner, ScanConfig
from app.services.notifier import notifier
from app.core.logger import get_logger
from dotenv import load_dotenv

# Load env variables
env_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
load_dotenv(dotenv_path=env_path)

logger = get_logger(__name__)


def print_signals(signals: list[dict], limit: int):
    """신호 결과를 테이블 형태로 출력"""
    display_count = limit if limit < len(signals) else len(signals)
    logger.info(f"[신호 결과] {len(signals)}개 종목 발견. 상위 {display_count if limit < len(signals) else '전체'} (장중 강도순)")
    logger.info("-" * 125)
    logger.info(f"{'Ticker':<8} | {'Close':<10} | {'Str(%)':<8} | {'Amt(B)':<8} | {'MA(20)':<10} | {'HIGH(20)':<10} | {'ATR(20)':<10} | {'STAGE':<5} | {'Name'}")
    logger.info("-" * 125)

    for s in signals[:limit]:
        logger.info(
            f"{s['ticker']:<8} | {s['close']:<10} | {s['strength']:<8} | "
            f"{s['amount_b']:<8} | {s['ma_20']:<10} | {s['high_20']:<10} | "
            f"{s['atr_20']:<10} | {s['stage']:<5} | {s['name']}"
        )
    logger.info("-" * 125)


def save_to_excel(signals: list[dict], target_date: str):
    """신호 결과를 엑셀 파일로 저장"""
    df = pd.DataFrame(signals)

    # 컬럼 정리
    output_columns = [
        'ticker', 'name', 'close', 'strength', 'amount_b',
        'ma_20', 'high_20', 'atr_20', 'stage'
    ]
    df = df.loc[:, ~df.columns.duplicated()]
    df = df[[col for col in output_columns if col in df.columns]]

    # 컬럼명 한글화
    df.columns = [
        '종목코드', '종목명', '종가', '강도(%)', '거래대금(억)',
        'MA(20)', 'HIGH(20)', 'ATR(20)', 'Stage'
    ]

    # 저장 경로
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    results_dir = os.path.join(project_root, 'results')
    os.makedirs(results_dir, exist_ok=True)

    date_str = target_date.replace('-', '')
    filepath = os.path.join(results_dir, f"signal_{date_str}.xlsx")

    try:
        df.to_excel(filepath, index=False, engine='openpyxl')
        logger.info(f"엑셀 결과 저장 완료: {filepath}")
    except PermissionError:
        logger.error(f"엑셀 저장 실패: 파일이 이미 열려 있습니다 ({filepath})")
    except Exception as e:
        logger.error(f"엑셀 저장 실패: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run Trend Following Strategy Signal Scanner")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--min_amount", type=int, default=5000000000,
                        help="Minimum transaction amount (default: 5,000,000,000 KRW)")
    parser.add_argument("--min_price", type=int, default=1000,
                        help="Minimum price filter (default: 1,000)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Number of results to show (0 for all, default: All)")
    parser.add_argument("--no-notify", action="store_true",
                        help="Telegram 알림 발송 생략")

    args = parser.parse_args()
    target_date = args.date if args.date else datetime.now().strftime("%Y-%m-%d")

    logger.info(f"전략 스캐너 시작: {target_date}")

    # 스캔 실행
    config = ScanConfig(
        target_date=target_date,
        min_amount=args.min_amount,
        min_price=args.min_price,
    )
    signals = strategy_scanner.scan(config)

    # 결과 출력
    limit = args.limit if args.limit > 0 else len(signals)
    if signals:
        print_signals(signals, limit)
        save_to_excel(signals, target_date)

    # Telegram 알림 발송
    if not args.no_notify and notifier.is_configured:
        notifier.send_signal_report(signals, target_date)


if __name__ == "__main__":
    main()
