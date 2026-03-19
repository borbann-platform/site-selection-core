from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Default to a placeholder, but will be overridden by .env file
    DATABASE_URL: str = "postgresql://user:password@localhost:5435/gisdb"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 30
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_STATEMENT_TIMEOUT_MS: int = 15000

    LOG_LEVEL: str = "INFO"

    # Object storage for scraped listing images
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "listing-images"
    MINIO_OBJECT_PREFIX: str = "scraped-listings"

    # JWT Settings
    JWT_SECRET_KEY: str = "change-this-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
