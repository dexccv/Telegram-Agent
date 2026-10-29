"""Unit tests untuk skrip setup wizard TeleAgent (setup_teleagent.py)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from setup_teleagent import (
    build_env_content,
    validate_telegram_token,
    validate_gemini_api_key,
    auto_detect_telegram_user_id,
)


def test_build_env_content() -> None:
    content = build_env_content(
        bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        user_id="987654321",
        gemini_key="AIzaSyTestGeminiKey123",
        groq_key="gsk_testgroqkey12345",
        default_provider="groq",
    )
    assert "TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11" in content
    assert "TELEGRAM_ALLOWED_USER_ID=987654321" in content
    assert "GEMINI_API_KEY=AIzaSyTestGeminiKey123" in content
    assert "GROQ_API_KEY=gsk_testgroqkey12345" in content
    assert "DEFAULT_AI_PROVIDER=groq" in content


def test_build_env_content_defaults() -> None:
    content = build_env_content(
        bot_token="123456:ABC",
        user_id="112233",
        gemini_key="AIzaSyTestGeminiKey123",
    )
    assert "DEFAULT_AI_PROVIDER=gemini" in content
    assert "GEMINI_API_KEY=AIzaSyTestGeminiKey123" in content
    assert "TELEGRAM_ALLOWED_USER_ID=112233" in content


@patch("urllib.request.urlopen")
def test_validate_telegram_token_success(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"ok": true, "result": {"id": 12345, "is_bot": true, "first_name": "TeleAgentBot", "username": "tele_agent_bot"}}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    ok, name = validate_telegram_token("12345:TOKEN")
    assert ok is True
    assert "@tele_agent_bot" in name


def test_validate_telegram_token_invalid_format() -> None:
    ok, name = validate_telegram_token("invalid_token_without_colon")
    assert ok is False
    assert "Format token tidak valid" in name


@patch("urllib.request.urlopen")
def test_validate_telegram_token_rejected_by_api(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"ok": false, "error_code": 401, "description": "Unauthorized"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    ok, desc = validate_telegram_token("12345:INVALID_TOKEN")
    assert ok is False
    assert "Unauthorized" in desc


@patch("urllib.request.urlopen")
def test_auto_detect_telegram_user_id_success(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"ok": true, "result": [{"update_id": 100, "message": {"from": {"id": 999888777, "first_name": "Teguh", "username": "teguh_dev"}, "text": "halo"}}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    ok, user_id, username = auto_detect_telegram_user_id("12345:TOKEN", timeout_seconds=2)
    assert ok is True
    assert user_id == "999888777"
    assert username == "teguh_dev"


@patch("urllib.request.urlopen")
def test_validate_gemini_api_key_success(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"models": [{"name": "models/gemini-2.5-flash"}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    ok, msg = validate_gemini_api_key("AIzaFakeKey")
    assert ok is True
    assert "Valid" in msg
