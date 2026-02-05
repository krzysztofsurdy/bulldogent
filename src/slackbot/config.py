from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="developer", min_length=1)
    slack_bot_token: str = Field(min_length=1)
    slack_app_token: str = Field(min_length=1)
    slack_signing_secret: str = Field(min_length=1)
    slack_reaction_acknowledged: str = Field(min_length=1)
    slack_reaction_handled: str = Field(min_length=1)
    slack_reaction_error: str = Field(min_length=1)
    openai_api_key: str = Field(min_length=1)
    openai_model: str = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )
