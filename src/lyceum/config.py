from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    database_url: str = 'sqlite:///./data/lyceum.db'
    telegram_bot_token: str = ''
    telegram_chat_id: str = ''
    cursor_api_key: str = ''
    # Сценарии флаг не читают. Адаптер выбирает build_summarizer снаружи.
    summarizer: str = 'fake'
