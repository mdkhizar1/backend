from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/netbanking"
    SECRET_KEY: str = "your-super-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    TRANSACTION_TOKEN_EXPIRE_MINUTES: int = 5
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "https://your-frontend.vercel.app"]

    class Config:
        env_file = ".env"


settings = Settings()
