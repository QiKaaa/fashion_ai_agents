import os
from typing import Any, Dict, Optional
from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

class Settings(BaseSettings):
    # API配置
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Qwen-VL-Plus模型配置
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_API_BASE_URL: str = os.getenv("QWEN_API_BASE_URL", "https://api.qwen.ai/v1")
    
    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", "")
    
    # PostgreSQL配置
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "fashion_ai")
    
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None
    
    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v
        values = info.data
        db_uri = PostgresDsn.build(
            scheme="postgresql",
            username=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_HOST"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )
        # 修复双斜杠问题，只替换路径中的双斜杠
        uri_str = str(db_uri)
        # 只替换路径部分的双斜杠，保持协议部分不变
        if "/fashion_ai" in uri_str:
            uri_str = uri_str.replace("//fashion_ai", "/fashion_ai")
        return uri_str
    
    # 会话配置
    SESSION_TTL: int = int(os.getenv("SESSION_TTL", "3600"))  # 会话超时时间，默认1小时
    
    # 阿里云百炼embedding配置
    ALIYUN_API_KEY: str = os.getenv("ALIYUN_API_KEY", "")
    ALIYUN_EMBEDDING_ENDPOINT: str = os.getenv("ALIYUN_EMBEDDING_ENDPOINT", "https://dashscope.aliyuncs.com")
    ALIYUN_EMBEDDING_MODEL: str = os.getenv("ALIYUN_EMBEDDING_MODEL", "multimodal-embedding-v1")
    
    # 向量化配置
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    # 应用配置
    PROJECT_NAME: str = "AI试衣多Agent智能体系统"
    
    model_config = {
        "case_sensitive": True
    }


settings = Settings()