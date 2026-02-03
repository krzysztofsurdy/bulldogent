from slackbot.config import Settings


def test_settings_loads_from_env(monkeypatch):
    settings = Settings()
    assert settings.slack_bot_token
    assert settings.slack_app_token
    assert settings.slack_signing_secret
    assert settings.slack_reaction_acknowledged
    assert settings.slack_reaction_handled
    assert settings.slack_reaction_error
    assert settings.aws_region
    assert settings.aws_bedrock_model_id
