from sqlalchemy import Column, BigInteger, String, Text, SmallInteger, DateTime
from sqlalchemy.sql import func
from app.models.database import Base


class Category(Base):
    """商品分类表"""
    __tablename__ = "categories"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    parent_id = Column(BigInteger, nullable=True, comment="父级分类ID")
    category_name = Column(String(100), nullable=False, comment="分类名称") 
    sort_order = Column(BigInteger, default=0, comment="排序")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted = Column(SmallInteger, default=0, comment="是否删除")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', parent_id={self.parent_id})>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "level": self.level,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# 定义分类常量
class CategoryTypes:
    """分类类型常量"""
    UPPER_CLOTHING = 23  # 上装父级ID
    LOWER_CLOTHING = 24  # 下装父级ID