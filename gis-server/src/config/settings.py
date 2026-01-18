from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Default to a placeholder, but will be overridden by .env file
    DATABASE_URL: str = "postgresql://user:password@localhost:5435/gisdb"

    # JWT Settings
    JWT_SECRET_KEY: str = "change-this-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
