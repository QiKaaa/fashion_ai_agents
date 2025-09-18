from sqlalchemy import Column, BigInteger, String, Text, DECIMAL, SmallInteger, DateTime, ARRAY, Float, JSON
from sqlalchemy.sql import func
from app.models.database import Base
from typing import Dict, Any, Optional, List

class ProductVectors(Base):
    """统一商品向量表，包含tag字段用于RAG筛选和向量字段用于相似性搜索"""
    __tablename__ = "product_vectors"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, nullable=False, unique=True, comment="商品ID")
    product_name = Column(String(255), nullable=False, comment="商品名称")
    description = Column(Text, nullable=True, comment="商品描述")
    image_gif = Column(String(1000), nullable=True, comment="商品图片URL")
    category_id = Column(BigInteger, nullable=True, comment="分类ID")
    brand = Column(String(255), nullable=True, comment="品牌")
    price = Column(DECIMAL(10, 2), nullable=True, comment="价格")
    is_recommended = Column(SmallInteger, default=0, comment="是否推荐")
    product_status = Column(SmallInteger, default=0, comment="商品状态")
    
    # RAG筛选字段（粗筛）
    scene = Column(String(50), nullable=True, comment="场景：casual/sports")
    color = Column(String(50), nullable=True, comment="颜色")
    style = Column(String(50), nullable=True, comment="风格")
    fit = Column(String(50), nullable=True, comment="版型")
    material = Column(String(50), nullable=True, comment="材质")
    season = Column(String(50), nullable=True, comment="季节")
    pattern = Column(String(50), nullable=True, comment="图案")
    
    # 向量字段（精筛）
    text_vector = Column(String, nullable=True, comment="文本向量，1024维（JSON格式存储）")
    image_vector = Column(String, nullable=True, comment="图片向量，1024维（JSON格式存储）")
    
    # 原始数据
    original_data = Column(JSON, nullable=True, comment="原始数据JSON，包含image_url和text_content")
    
    # 状态和时间戳
    vector_status = Column(SmallInteger, default=0, comment="向量状态：0-未处理，1-文本生成，2-图片生成，3-完成")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<ProductVectors(product_id={self.product_id}, product_name='{self.product_name}')>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "description": self.description,
            "image_gif": self.image_gif,
            "category_id": self.category_id,
            "brand": self.brand,
            "price": float(self.price) if self.price else None,
            "is_recommended": self.is_recommended,
            "product_status": self.product_status,
            "scene": self.scene,
            "color": self.color,
            "style": self.style,
            "fit": self.fit,
            "material": self.material,
            "season": self.season,
            "pattern": self.pattern,
            "text_vector": self.text_vector,
            "image_vector": self.image_vector,
            "original_data": self.original_data,
            "vector_status": self.vector_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
