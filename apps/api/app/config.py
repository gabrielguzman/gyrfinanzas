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
    # Login (producción). Sin hash, la app queda abierta (uso local en tu red).
    # Generar el hash: python -m app.auth "tu contraseña"
    app_password_hash: str = ""
    secret_key: str = ""          # para firmar la sesión; obligatoria si hay contraseña
    cookie_secure: bool = False   # True detrás de HTTPS
    sesion_dias: int = 90
    usuarios_habilitados: bool = False
    app_url: str = "http://localhost:3000"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""


settings = Settings()
