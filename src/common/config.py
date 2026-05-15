from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str
    telegram_bot_token: str
    telegram_chat_id: str
    google_sheet_id: str
    google_service_account_json: str
    linkedin_access_token: str = ""
    linkedin_person_id: str = ""


settings = Settings()  # type: ignore[call-arg]
