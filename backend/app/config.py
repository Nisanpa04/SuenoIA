"""Configuración por variables de entorno (Pydantic Settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    pg_host: str = "localhost"
    pg_port: int = 5433
    pg_user: str = "suenoia"
    pg_password: str = "suenoia_pass"
    pg_database: str = "suenoia"

    # --- Elasticsearch ---
    es_url: str = "http://localhost:19200"

    # --- Kafka ---
    kafka_bootstrap: str = "localhost:19092"
    kafka_alerts_topic: str = "alerts.detected"

    # --- Anthropic ---
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens: int = 1024

    # --- Telegram (opcional) ---
    telegram_bot_token: str = ""

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} "
            f"dbname={self.pg_database} user={self.pg_user} "
            f"password={self.pg_password}"
        )


settings = Settings()
