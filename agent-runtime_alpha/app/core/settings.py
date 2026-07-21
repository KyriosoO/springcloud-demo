"""应用配置，从指定前缀环境变量加载。"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从指定前缀环境变量加载。"""
    llm_base_url: str = Field(min_length=1)
    llm_api_key: SecretStr
    llm_model: str = Field(min_length=1)
    llm_timeout_seconds: float = Field(default=15.0, gt=0)
    runtime_shared_key: SecretStr = Field(min_length=16)
    # 查询路由置信度低于此阈值时自动降级为澄清。
    route_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存的配置单例工厂函数。"""
    return Settings()
