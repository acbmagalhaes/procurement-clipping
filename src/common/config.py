from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REQUIRED = {"anthropic_api_key", "telegram_bot_token", "telegram_chat_id", "google_sheet_id", "google_service_account_json"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    google_sheet_id: str
    google_service_account_json: str
    # LinkedIn (optional — required only for automatic posting)
    linkedin_access_token: str = ""
    linkedin_author_urn: str = ""

    @field_validator("anthropic_api_key", "telegram_bot_token", "telegram_chat_id", "google_sheet_id", "google_service_account_json")
    @classmethod
    def must_not_be_empty(cls, v: str, info) -> str:
        if not v:
            raise ValueError(f"{info.field_name} is required but was empty or not set")
        return v


settings = Settings()  # type: ignore[call-arg]
