from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str = "dev-secret-change-me"
    access_ttl_min: int = 20
    refresh_ttl_days: int = 14
    order_rate_limit_min: int = 3

    class Config:
        env_prefix = ""
        case_sensitive = False

settings = Settings()
