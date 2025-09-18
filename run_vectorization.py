#!/usr/bin/env python3
"""
统一表向量化运行脚本
从数据库products表获取数据并存储到统一的product_vectors表
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.vectorization.data_importer import SQLDataImporter
from app.services.vectorization.embedding_service import AliyunEmbeddingService
from app.services.vectorization.vector_storage_service import VectorStorageService
from app.core.logging import app_logger


async def run_vectorization():
    """运行统一表向量化并存储到数据库"""
    print("开始统一表向量化处理...")
    print("将从数据库products表获取数据并存储到product_vectors表")
    
    try:
        # 创建服务
        data_importer = SQLDataImporter()
        embedding_service = AliyunEmbeddingService()
        vector_storage = VectorStorageService()
        
        # 1. 从数据库获取产品数据
        print("\n[步骤1] 从数据库获取产品数据...")
        products = data_importer.get_products_from_database()

        if not products:
            print("没有找到有效的产品数据")
            return

        print(f"成功获取 {len(products)} 个产品")
        print("注意：请确保已执行 data/vectors/create_unified_table.sql 创建统一表")
        
        # 2. 批量向量化并存储到统一表
        print("\n[步骤2] 开始向量化并存储到统一表...")
        print("  - product_vectors: 存储商品信息、tag字段和向量数据")
        success_count = 0
        failed_count = 0
        
        for i, product in enumerate(products):
            try:
                # 构建文本描述
                text_description = f"{product.get('product_name', '')} {product.get('description', '')}"
                
                # 提取tag信息（从数据中解析）
                scene = product.get("scene", "casual")
                color = product.get("color", "")
                style = product.get("style", "casual")
                fit = product.get("fit", "regular")
                material = product.get("material", "cotton")
                season = product.get("season", "all")
                pattern = product.get("pattern", "solid")
                
                # 存储到统一表
                success = await vector_storage.store_product_vectors(
                    product_id=product["id"],
                    product_name=product["product_name"],
                    description=text_description,
                    image_url=product.get("image_gif", ""),
                    category_id=product.get("category_id"),
                    brand=product.get("brand"),
                    price=product.get("price"),
                    is_recommended=product.get("is_recommended", 0),
                    product_status=product.get("product_status", 0),
                    scene=scene,
                    color=color,
                    style=style,
                    fit=fit,
                    material=material,
                    season=season,
                    pattern=pattern
                )
                
                if success:
                    success_count += 1
                    print(f"[成功] 产品 {product['id']}: {product['product_name']}")
                else:
                    failed_count += 1
                    print(f"[失败] 产品 {product['id']}: 存储失败")
                
                # 每处理10个产品显示进度
                if (i + 1) % 10 == 0:
                    print(f"进度: {i + 1}/{len(products)}")
                
                # 添加延迟避免API限制
                await asyncio.sleep(0.5)
                
            except Exception as e:
                failed_count += 1
                print(f"[失败] 产品 {product.get('id')}: {e}")
        
        # 3. 显示结果
        print(f"\n=== 向量化完成 ===")
        print(f"总产品数: {len(products)}")
        print(f"成功处理: {success_count}")
        print(f"失败数量: {failed_count}")
        
        # 4. 显示完成信息
        print(f"\n数据库统计:")
        print(f"  - 成功处理: {success_count} 个商品")
        print(f"  - 失败数量: {failed_count} 个商品")
        
        print(f"\n统一表向量化完成！数据已存储到product_vectors表中：")
        print(f"  - 商品基本信息：名称、描述、图片URL等")
        print(f"  - Tag字段：scene、color、style等（用于RAG粗筛）")
        print(f"  - 向量字段：text_vector、image_vector（用于RAG精筛）")
        print(f"  - 原始数据：JSON格式存储的原始信息")
        print(f"\n现在您可以使用RAG系统进行精确筛选和向量相似性搜索！")
            
    except Exception as e:
        print(f"运行失败: {e}")
        app_logger.error(f"向量化运行失败: {e}")


if __name__ == "__main__":
    asyncio.run(run_vectorization())