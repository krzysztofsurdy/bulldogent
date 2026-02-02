import pytest
from pydantic import ValidationError

from slackbot.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("SLACK_APP_TOKEN", "test_app_token")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_signing_secret")
    monkeypatch.setenv("AWS_REGION", "test_region")
    monkeypatch.setenv("AWS_BEDROCK_MODEL_ID", "test_bedrock_model_id")

    settings = Settings()
    assert settings.slack_bot_token == "test_bot_token"
    assert settings.slack_app_token == "test_app_token"


def test_settings_raises_error_when_fields_missing(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test_bot_token")
    monkeypatch.setenv("SLACK_APP_TOKEN", "test_app_token")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_signing_secret")
    monkeypatch.setenv("AWS_REGION", "test_region")
    with pytest.raises(ValidationError):
        Settings()
