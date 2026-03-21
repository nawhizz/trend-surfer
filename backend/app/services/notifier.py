"""
알림 서비스

전략 신호 결과를 Telegram으로 발송합니다.
"""

import os
from datetime import datetime
from typing import Optional

import requests

from app.core.logger import get_logger

logger = get_logger(__name__)

# Telegram 설정 (환경 변수)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class Notifier:
    """Telegram 알림 발송 서비스"""

    def __init__(
        self,
        bot_token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def is_configured(self) -> bool:
        """Telegram 설정이 완료되었는지 확인"""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Telegram 메시지 발송

        Args:
            text: 메시지 내용 (HTML 또는 Markdown)
            parse_mode: 파싱 모드 (HTML 또는 MarkdownV2)

        Returns:
            발송 성공 여부
        """
        if not self.is_configured:
            logger.warning("Telegram 설정이 없습니다. TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID를 확인하세요.")
            return False

        url = TELEGRAM_API_URL.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram 메시지 발송 성공")
                return True
            else:
                logger.error(f"Telegram 발송 실패: {resp.status_code} - {resp.text}")
                return False
        except requests.Timeout:
            logger.error("Telegram 발송 시간 초과")
            return False
        except requests.ConnectionError:
            logger.error("Telegram 서버 연결 실패")
            return False
        except requests.RequestException as e:
            logger.error(f"Telegram 발송 오류: {e}")
            return False

    def send_signal_report(
        self,
        signals: list[dict],
        target_date: str,
        max_display: int = 20,
    ) -> bool:
        """
        전략 신호 결과 리포트 발송

        Args:
            signals: 신호 리스트 (strategy_scanner.scan() 결과)
            target_date: 기준 날짜
            max_display: 최대 표시 종목 수

        Returns:
            발송 성공 여부
        """
        if not signals:
            text = (
                f"📊 <b>TrendSurfer 신호 리포트</b>\n"
                f"📅 {target_date}\n\n"
                f"오늘 조건을 충족하는 종목이 없습니다."
            )
            return self.send_message(text)

        # 헤더
        lines = [
            f"📊 <b>TrendSurfer 신호 리포트</b>",
            f"📅 {target_date} | {len(signals)}개 종목 발견",
            "",
        ]

        # 종목 리스트 (강도순 상위 N개)
        for i, s in enumerate(signals[:max_display], 1):
            stage_emoji = self._stage_emoji(s.get("stage", 0))
            lines.append(
                f"{i}. <b>{s['name']}</b> ({s['ticker']})\n"
                f"   종가 {s['close']:,} | 강도 {s['strength']}% | "
                f"거래대금 {s['amount_b']}억 {stage_emoji}"
            )

        if len(signals) > max_display:
            lines.append(f"\n... 외 {len(signals) - max_display}개 종목")

        text = "\n".join(lines)

        # Telegram 메시지 길이 제한 (4096자)
        if len(text) > 4000:
            text = text[:4000] + "\n\n(메시지 길이 초과로 일부 생략)"

        return self.send_message(text)

    def send_daily_summary(
        self,
        target_date: str,
        signal_count: int,
        market_status: Optional[dict] = None,
    ) -> bool:
        """
        일일 루틴 완료 요약 발송

        Args:
            target_date: 기준 날짜
            signal_count: 발견된 신호 수
            market_status: 시장 상태 (선택)

        Returns:
            발송 성공 여부
        """
        lines = [
            f"✅ <b>일일 루틴 완료</b>",
            f"📅 {target_date}",
            "",
        ]

        if market_status:
            kospi_status = "🟢" if market_status.get("kospi_above_ma") else "🔴"
            kosdaq_status = "🟢" if market_status.get("kosdaq_above_ma") else "🔴"
            lines.append(
                f"시장: KOSPI {kospi_status} | KOSDAQ {kosdaq_status}"
            )

        lines.append(f"신호: {signal_count}개 종목 발견")

        return self.send_message("\n".join(lines))

    @staticmethod
    def _stage_emoji(stage: int) -> str:
        """EMA 스테이지에 따른 이모지"""
        stage_map = {
            1: "🟢S1",  # 안정 상승
            2: "🟡S2",  # 하락 변화1
            3: "🟠S3",  # 하락 변화2
            4: "🔴S4",  # 안정 하락
            5: "🟠S5",  # 상승 변화1
            6: "🟡S6",  # 상승 변화2
        }
        return stage_map.get(stage, "⚪S0")


# 싱글톤 인스턴스
notifier = Notifier()
