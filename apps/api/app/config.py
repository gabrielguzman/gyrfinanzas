from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gyr:gyr@localhost:5432/gyrfinanzas"
    upload_dir: str = "./uploads"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 15
    telegram_token: str = ""
    telegram_codigo: str = ""
    # Lectura de resúmenes con IA (opcional). Sin clave se usan reglas.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"


settings = Settings()
