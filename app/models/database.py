from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# 创建数据库引擎
# 强制客户端编码为 UTF8，避免在 Windows 上回落为 GBK 造成解码错误
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    connect_args={"options": "-c client_encoding=UTF8"}
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基础模型类
Base = declarative_base()

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()