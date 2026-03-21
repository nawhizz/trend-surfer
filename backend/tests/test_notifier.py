"""
Notifier 단위 테스트

실제 Telegram API 호출 없이 메시지 포매팅 및 설정 검증
"""

import pytest

from app.services.notifier import Notifier


@pytest.fixture
def notifier_unconfigured():
    return Notifier(bot_token="", chat_id="")


@pytest.fixture
def notifier_configured():
    return Notifier(bot_token="fake_token", chat_id="fake_chat")


class TestConfiguration:
    def test_unconfigured(self, notifier_unconfigured):
        """토큰/챗ID 없으면 is_configured=False"""
        assert notifier_unconfigured.is_configured is False

    def test_configured(self, notifier_configured):
        """토큰/챗ID 있으면 is_configured=True"""
        assert notifier_configured.is_configured is True

    def test_send_skips_when_unconfigured(self, notifier_unconfigured):
        """미설정 시 send_message는 False 반환"""
        result = notifier_unconfigured.send_message("test")
        assert result is False


class TestStageEmoji:
    def test_stage_1(self):
        assert "🟢" in Notifier._stage_emoji(1)

    def test_stage_4(self):
        assert "🔴" in Notifier._stage_emoji(4)

    def test_unknown_stage(self):
        assert "⚪" in Notifier._stage_emoji(99)


class TestSignalReport:
    def test_empty_signals(self, notifier_configured, mocker):
        """빈 신호 리포트 발송"""
        mock_send = mocker.patch.object(notifier_configured, "send_message", return_value=True)
        result = notifier_configured.send_signal_report([], "2025-01-01")
        assert result is True
        sent_text = mock_send.call_args[0][0]
        assert "없습니다" in sent_text

    def test_signal_report_format(self, notifier_configured, mocker):
        """신호 리포트 포맷 검증"""
        mock_send = mocker.patch.object(notifier_configured, "send_message", return_value=True)
        signals = [
            {
                "ticker": "005930", "name": "삼성전자", "close": 72000,
                "strength": 2.5, "amount_b": 700, "ma_20": 70000,
                "high_20": 71000, "atr_20": 1500, "stage": 1,
            }
        ]
        notifier_configured.send_signal_report(signals, "2025-01-01")
        sent_text = mock_send.call_args[0][0]
        assert "삼성전자" in sent_text
        assert "005930" in sent_text
        assert "1개 종목" in sent_text

    def test_long_report_truncated(self, notifier_configured, mocker):
        """긴 메시지는 4000자에서 잘림"""
        mock_send = mocker.patch.object(notifier_configured, "send_message", return_value=True)
        signals = [
            {
                "ticker": f"{i:06d}", "name": f"종목_{i}", "close": 10000 + i,
                "strength": 1.0, "amount_b": 100, "ma_20": 9000,
                "high_20": 9500, "atr_20": 500, "stage": 1,
            }
            for i in range(100)
        ]
        notifier_configured.send_signal_report(signals, "2025-01-01", max_display=100)
        sent_text = mock_send.call_args[0][0]
        assert len(sent_text) <= 4096
