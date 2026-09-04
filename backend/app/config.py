from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    telegram_bot_token: str
    bot_api_token: str
    web_origin: str = "http://localhost:3000"


settings = Settings()
