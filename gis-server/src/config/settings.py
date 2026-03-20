from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Default to a placeholder, but will be overridden by .env file
    DATABASE_URL: str = "postgresql://user:password@localhost:5435/gisdb"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_STATEMENT_TIMEOUT_MS: int = 15000
    DB_USE_PGBOUNCER: bool = False

    CACHE_BACKEND: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_KEY_PREFIX: str = "site_select_core"
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 0.2

    LOG_LEVEL: str = "INFO"

    ANALYTICS_DATAFRAME_CACHE_TTL_SECONDS: int = 600
    ANALYTICS_DATAFRAME_CACHE_MAX_ENTRIES: int = 8

    LOCATION_INTELLIGENCE_CACHE_TTL_SECONDS: int = 900
    LOCATION_INTELLIGENCE_CACHE_MAX_ENTRIES: int = 2000

    CONVERSATION_CACHE_MAX_SESSIONS: int = 500
    CONVERSATION_CACHE_MAX_MESSAGES_PER_SESSION: int = 200

    AGENT_RUNTIME_CACHE_MAX_ENTRIES: int = 8

    LISTINGS_TILE_CACHE_TTL_SECONDS: int = 600
    LISTINGS_TILE_CACHE_MAX_ENTRIES: int = 2000
    LISTINGS_TILE_MATVIEW_REFRESH_SECONDS: int = 600
    LISTINGS_TILE_MATVIEW_STALE_SECONDS: int = 900

    ANALYTICS_TILE_CACHE_TTL_SECONDS: int = 3600
    ANALYTICS_TILE_CACHE_MAX_ENTRIES: int = 2000

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
