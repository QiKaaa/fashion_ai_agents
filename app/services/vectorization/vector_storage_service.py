"""
向量存储服务
用于管理商品向量数据的存储和检索
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.database import get_db
from app.models.product_vectors import ProductVectors
from app.services.vectorization.embedding_service import AliyunEmbeddingService
from app.core.logging import app_logger


class VectorStorageService:
    """向量存储服务"""
    
    def __init__(self):
        self.embedding_service = AliyunEmbeddingService()
    
    async def store_product_vectors(
        self, 
        product_id: int, 
        product_name: str,
        description: str,
        image_url: str,
        category_id: int = None,
        brand: str = None,
        price: float = None,
        is_recommended: int = 0,
        product_status: int = 0,
        scene: str = None,
        color: str = None,
        style: str = None,
        fit: str = None,
        material: str = None,
        season: str = None,
        pattern: str = None
    ) -> bool:
        """存储商品向量数据到统一表
        
        Args:
            product_id: 商品ID
            product_name: 商品名称
            description: 商品描述
            image_url: 图片URL
            category_id: 分类ID
            brand: 品牌
            price: 价格
            is_recommended: 是否推荐
            product_status: 商品状态
            scene: 场景
            color: 颜色
            style: 风格
            fit: 版型
            material: 材质
            season: 季节
            pattern: 图案
            
        Returns:
            是否存储成功
        """
        try:
            # 拼接文本内容
            text_content = f"{product_name} {description}"
            
            # 准备原始数据 - 只包含图片URL和拼接后的文本
            original_data = {
                "image_url": image_url,
                "text_content": text_content
            }
            
            # 生成向量
            text_vector = await self.embedding_service.embed_text(text_content)
            image_vector = await self.embedding_service.embed_image(image_url)
            
            # 存储到数据库
            with next(get_db()) as db:
                # 查询现有记录
                existing_record = db.query(ProductVectors).filter(
                    ProductVectors.product_id == product_id
                ).first()
                
                if existing_record:
                    # 更新现有记录
                    existing_record.product_name = product_name
                    existing_record.description = description
                    existing_record.image_gif = image_url
                    existing_record.category_id = category_id
                    existing_record.brand = brand
                    existing_record.price = price
                    existing_record.is_recommended = is_recommended
                    existing_record.product_status = product_status
                    existing_record.scene = scene
                    existing_record.color = color
                    existing_record.style = style
                    existing_record.fit = fit
                    existing_record.material = material
                    existing_record.season = season
                    existing_record.pattern = pattern
                    existing_record.text_vector = json.dumps(text_vector) if text_vector is not None else None
                    existing_record.image_vector = json.dumps(image_vector) if image_vector is not None else None
                    existing_record.original_data = original_data
                    existing_record.vector_status = 3
                else:
                    # 创建新记录
                    vectors_record = ProductVectors(
                        product_id=product_id,
                        product_name=product_name,
                        description=description,
                        image_gif=image_url,
                        category_id=category_id,
                        brand=brand,
                        price=price,
                        is_recommended=is_recommended,
                        product_status=product_status,
                        scene=scene,
                        color=color,
                        style=style,
                        fit=fit,
                        material=material,
                        season=season,
                        pattern=pattern,
                        text_vector=json.dumps(text_vector) if text_vector is not None else None,
                        image_vector=json.dumps(image_vector) if image_vector is not None else None,
                        original_data=original_data,
                        vector_status=3
                    )
                    db.add(vectors_record)
                
                db.commit()
                app_logger.info(f"成功存储商品 {product_id} 的向量数据到统一表")
                return True
                
        except Exception as e:
            app_logger.error(f"存储商品向量数据失败: {e}")
            return False
    
    
    
    
