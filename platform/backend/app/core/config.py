"""Configuracao centralizada via Pydantic Settings."""


from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    DEBUG: bool = False
    APP_NAME: str = "Namastex Platform"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/namastex"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT (RS256)
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"  # Migrar para RS256 com par de chaves em producao
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption (Fernet — SEPARADA do JWT secret)
    ENCRYPTION_KEY: str = "change-me-encryption-key"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Omni
    OMNI_API_URL: str = "http://localhost:8882/api/v2"
    OMNI_API_KEY: str = ""
    OMNI_WEBHOOK_SECRET: str = ""  # HMAC shared secret

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5


settings = Settings()
