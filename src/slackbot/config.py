from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    slack_bot_token: str = Field(min_length=1)
    slack_app_token: str = Field(min_length=1)
    slack_signing_secret: str = Field(min_length=1)
    aws_region: str = Field(min_length=1)
    aws_bedrock_model_id: str = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )
