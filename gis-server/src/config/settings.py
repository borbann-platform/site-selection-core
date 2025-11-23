from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Default to a placeholder, but will be overridden by .env file
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/gisdb"

    class Config:
        env_file = ".env"


settings = Settings()
