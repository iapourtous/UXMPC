from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://mongodb-uxmpc:27017"
    database_name: str = "uxmcp"
    mcp_server_url: str = "http://api:8000/mcp"
    redis_url: str = "redis://redis:6379"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()