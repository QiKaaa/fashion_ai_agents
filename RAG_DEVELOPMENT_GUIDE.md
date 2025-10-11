# RAG开发工作指南

## 概述

本文档为RAG（检索增强生成）团队提供详细的数据表结构和使用指南，帮助快速开展RAG功能开发。

## 数据库表结构

### product_vectors 表

这是统一的产品向量表，包含了所有RAG功能需要的数据字段。

#### 表结构说明

```sql
CREATE TABLE product_vectors (
    -- 基础字段
    id BIGSERIAL PRIMARY KEY,                    -- 主键ID
    product_id BIGINT UNIQUE NOT NULL,          -- 商品ID（与products表对应）
    product_name VARCHAR(255) NOT NULL,         -- 商品名称
    description TEXT,                           -- 商品描述
    image_gif VARCHAR(1000),                    -- 商品图片URL
    category_id BIGINT,                         -- 分类ID
    brand VARCHAR(255),                         -- 品牌
    price DECIMAL(10, 2),                       -- 价格
    is_recommended SMALLINT DEFAULT 0,          -- 是否推荐
    product_status SMALLINT DEFAULT 0,          -- 商品状态
  
    -- RAG筛选字段（粗筛）可以考虑使用INDEX
    scene VARCHAR(50),                          -- 场景：casual/sports
    color VARCHAR(50),                          -- 颜色
    style VARCHAR(50),                          -- 风格
    fit VARCHAR(50),                            -- 版型
    material VARCHAR(50),                       -- 材质
    season VARCHAR(50),                         -- 季节
    pattern VARCHAR(50),                        -- 图案
  
    -- 向量字段（精筛）
    text_vector TEXT,                           -- 文本向量，1024维（JSON格式存储）
    image_vector TEXT,                          -- 图片向量，1024维（JSON格式存储）
  
    -- 原始数据
    original_data JSONB,                        -- 原始数据JSON，包含image_url和text_content
  
    -- 状态和时间戳
    vector_status SMALLINT DEFAULT 0,           -- 向量状态：0-未处理，1-文本生成，2-图片生成，3-完成
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## 字段详细说明

### 1. 基础商品信息字段

| 字段名             | 类型          | 说明         | 示例                            |
| ------------------ | ------------- | ------------ | ------------------------------- |
| `product_id`     | BIGINT        | 商品唯一标识 | 12345                           |
| `product_name`   | VARCHAR(255)  | 商品名称     | "Nike Air Max 270"              |
| `description`    | TEXT          | 商品详细描述 | "舒适的运动鞋..."               |
| `image_gif`      | VARCHAR(1000) | 商品图片URL  | "https://example.com/image.jpg" |
| `category_id`    | BIGINT        | 商品分类ID   | 3                               |
| `brand`          | VARCHAR(255)  | 品牌名称     | "Nike"                          |
| `price`          | DECIMAL(10,2) | 商品价格     | 299.00                          |
| `is_recommended` | SMALLINT      | 是否推荐商品 | 1                               |
| `product_status` | SMALLINT      | 商品状态     | 1                               |

### 2. RAG筛选字段（粗筛）

这些字段用于快速筛选，减少需要向量相似性搜索的数据量。

| 字段名       | 类型        | 说明     | 可能值                                    |
| ------------ | ----------- | -------- | ----------------------------------------- |
| `scene`    | VARCHAR(50) | 使用场景 | `casual`, `sports`                    |
| `color`    | VARCHAR(50) | 颜色     | `黑色`, `白色`, `红色`, `蓝色` 等 |
| `style`    | VARCHAR(50) | 风格     | `休闲`, `运动`, `正式` 等           |
| `fit`      | VARCHAR(50) | 版型     | `宽松`, `修身`, `合身` 等           |
| `material` | VARCHAR(50) | 材质     | `棉`, `涤纶`, `牛仔` 等             |
| `season`   | VARCHAR(50) | 季节     | `春`, `夏`, `秋`, `冬`, `all`   |
| `pattern`  | VARCHAR(50) | 图案     | `纯色`, `条纹`, `印花` 等           |

### 3. 向量字段（精筛）

这些字段存储1024维的向量数据，用于精确的相似性搜索。

| 字段名           | 类型 | 说明     | 格式                       |
| ---------------- | ---- | -------- | -------------------------- |
| `text_vector`  | TEXT | 文本向量 | JSON数组格式，1024个浮点数 |
| `image_vector` | TEXT | 图片向量 | JSON数组格式，1024个浮点数 |

**向量数据格式示例：**

```json
[-0.000742898671887815, -0.03806854039430618, -0.010234218090772629, ...]
```

### 4. 原始数据字段

| 字段名            | 类型  | 说明     | 格式                                  |
| ----------------- | ----- | -------- | ------------------------------------- |
| `original_data` | JSONB | 原始数据 | JSON对象，包含image_url和text_content |

**原始数据格式示例：**

```json
{
  "image_url": "https://example.com/image.jpg",
  "text_content": "商品名称 商品描述"
}
```

### 5. 状态字段

| 字段名            | 类型     | 说明         | 可能值                                   |
| ----------------- | -------- | ------------ | ---------------------------------------- |
| `vector_status` | SMALLINT | 向量处理状态 | 0-未处理, 1-文本生成, 2-图片生成, 3-完成 |

## 推荐索引策略

### 1. 基础查询索引

```sql
-- 商品ID索引（主键，通常自动创建）
CREATE INDEX idx_product_vectors_product_id ON product_vectors(product_id);

-- 品牌索引
CREATE INDEX idx_product_vectors_brand ON product_vectors(brand);

-- 分类索引
CREATE INDEX idx_product_vectors_category_id ON product_vectors(category_id);

-- 价格索引
CREATE INDEX idx_product_vectors_price ON product_vectors(price);
```

### 2. RAG筛选字段索引

```sql
-- 场景索引
CREATE INDEX idx_product_vectors_scene ON product_vectors(scene);

-- 颜色索引
CREATE INDEX idx_product_vectors_color ON product_vectors(color);

-- 风格索引
CREATE INDEX idx_product_vectors_style ON product_vectors(style);

-- 版型索引
CREATE INDEX idx_product_vectors_fit ON product_vectors(fit);

-- 材质索引
CREATE INDEX idx_product_vectors_material ON product_vectors(material);

-- 季节索引
CREATE INDEX idx_product_vectors_season ON product_vectors(season);

-- 图案索引
CREATE INDEX idx_product_vectors_pattern ON product_vectors(pattern);
```

### 3. 向量相似性搜索索引（如果使用pgvector）

```sql
-- 文本向量索引
CREATE INDEX idx_product_vectors_text_vector ON product_vectors 
USING ivfflat (text_vector vector_cosine_ops) WITH (lists = 100);

-- 图片向量索引
CREATE INDEX idx_product_vectors_image_vector ON product_vectors 
USING ivfflat (image_vector vector_cosine_ops) WITH (lists = 100);
```

## 查询示例

### 1. 基础筛选查询

```sql
-- 按场景和颜色筛选
SELECT * FROM product_vectors 
WHERE scene = 'casual' 
  AND color = '黑色' 
  AND price BETWEEN 100 AND 500;

-- 按品牌和风格筛选
SELECT * FROM product_vectors 
WHERE brand = 'Nike' 
  AND style = '运动' 
  AND season = '夏';
```

### 2. 向量相似性搜索

```sql
-- 文本向量相似性搜索（使用pgvector）
SELECT *, text_vector <-> query_vector AS distance 
FROM product_vectors 
WHERE scene = 'casual'
ORDER BY text_vector <-> query_vector 
LIMIT 10;

-- 图片向量相似性搜索
SELECT *, image_vector <-> query_vector AS distance 
FROM product_vectors 
WHERE color = '黑色'
ORDER BY image_vector <-> query_vector 
LIMIT 10;
```

### 3. 组合查询（粗筛 + 精筛）

```sql
-- 先按标签粗筛，再按向量精筛
SELECT *, text_vector <-> query_vector AS distance 
FROM product_vectors 
WHERE scene = 'casual' 
  AND color = '黑色' 
  AND style = '休闲'
ORDER BY text_vector <-> query_vector 
LIMIT 10;
```

## Python使用示例

### 1. 基础查询

```python
from sqlalchemy.orm import Session
from app.models.product_vectors import ProductVectors
from app.models.database import get_db

def search_products_by_tags(scene: str, color: str, limit: int = 10):
    """按标签筛选商品"""
    with next(get_db()) as db:
        products = db.query(ProductVectors).filter(
            ProductVectors.scene == scene,
            ProductVectors.color == color
        ).limit(limit).all()
  
        return [product.to_dict() for product in products]
```

### 2. 向量相似性搜索

```python
import json
import numpy as np
from sqlalchemy import text

def search_similar_products(query_vector: list, limit: int = 10):
    """向量相似性搜索"""
    with next(get_db()) as db:
        # 将查询向量转换为JSON字符串
        query_vector_json = json.dumps(query_vector)
  
        # 使用SQL进行向量相似性搜索
        result = db.execute(text("""
            SELECT *, 
                   text_vector <-> :query_vector AS distance
            FROM product_vectors 
            WHERE vector_status = 3
            ORDER BY text_vector <-> :query_vector 
            LIMIT :limit
        """), {
            'query_vector': query_vector_json,
            'limit': limit
        })
  
        return [dict(row) for row in result]
```

### 3. 组合搜索

```python
def hybrid_search(scene: str, color: str, query_vector: list, limit: int = 10):
    """混合搜索：标签筛选 + 向量相似性"""
    with next(get_db()) as db:
        query_vector_json = json.dumps(query_vector)
  
        result = db.execute(text("""
            SELECT *, 
                   text_vector <-> :query_vector AS distance
            FROM product_vectors 
            WHERE scene = :scene 
              AND color = :color
              AND vector_status = 3
            ORDER BY text_vector <-> :query_vector 
            LIMIT :limit
        """), {
            'scene': scene,
            'color': color,
            'query_vector': query_vector_json,
            'limit': limit
        })
  
        return [dict(row) for row in result]
```

## 性能优化建议

### 1. 查询优化

- **先粗筛后精筛**：使用标签字段先筛选出候选集，再使用向量搜索
- **合理使用索引**：根据查询模式创建合适的索引
- **限制结果数量**：使用LIMIT限制返回结果数量

### 2. 向量搜索优化

- **使用pgvector扩展**：如果可能，使用pgvector进行向量相似性搜索
- **调整索引参数**：根据数据量调整ivfflat索引的lists参数
- **批量处理**：对于大量查询，考虑批量处理

### 3. 缓存策略

- **结果缓存**：对常见查询结果进行缓存
- **向量缓存**：对频繁使用的查询向量进行缓存

## 数据质量检查

### 1. 检查向量数据完整性

```sql
-- 检查向量数据是否完整
SELECT 
    COUNT(*) as total_products,
    COUNT(text_vector) as text_vectors,
    COUNT(image_vector) as image_vectors,
    COUNT(CASE WHEN vector_status = 3 THEN 1 END) as completed_vectors
FROM product_vectors;
```

### 2. 检查标签数据分布

```sql
-- 检查场景分布
SELECT scene, COUNT(*) as count 
FROM product_vectors 
GROUP BY scene 
ORDER BY count DESC;

-- 检查颜色分布
SELECT color, COUNT(*) as count 
FROM product_vectors 
GROUP BY color 
ORDER BY count DESC;
```

## 按照RAG开发指南的具体实现步骤

### 第一步：创建RAG检索服务

根据指南中的Python示例，创建 `app/services/rag_service.py`：

```python
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from app.models.database import get_db
from app.services.vectorization.embedding_service import AliyunEmbeddingService
from app.core.logging import app_logger

class RAGService:
    """RAG检索服务，实现向量相似性搜索"""
    
    def __init__(self):
        self.embedding_service = AliyunEmbeddingService()
    
    async def search_similar_products(
        self, 
        query_text: str, 
        query_image: str,
        filters: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """混合搜索：标签筛选 + 向量相似性"""
        
        try:
            # 1. 向量化查询
            text_vector = await self.embedding_service.embed_text(query_text)
            image_vector = await self.embedding_service.embed_image(query_image)
            
            # 2. 构建查询条件
            where_conditions = ["vector_status = 3"]  # 只查询已完成的向量
            params = {
                'text_vector': json.dumps(text_vector),
                'image_vector': json.dumps(image_vector),
                'limit': limit
            }
            
            # 添加标签筛选条件
            if 'scene' in filters and filters['scene']:
                where_conditions.append("scene = :scene")
                params['scene'] = filters['scene']
            
            if 'color' in filters and filters['color']:
                where_conditions.append("color = :color")
                params['color'] = filters['color']
            
            if 'style' in filters and filters['style']:
                where_conditions.append("style = :style")
                params['style'] = filters['style']
            
            if 'max_price' in filters and filters['max_price']:
                where_conditions.append("price <= :max_price")
                params['max_price'] = filters['max_price']
            
            # 3. 执行混合搜索
            where_clause = " AND ".join(where_conditions)
            
            with next(get_db()) as db:
                result = db.execute(text(f"""
                    SELECT *, 
                           text_vector <-> :text_vector AS text_distance,
                           image_vector <-> :image_vector AS image_distance
                    FROM product_vectors 
                    WHERE {where_clause}
                    ORDER BY (text_distance + image_distance) / 2
                    LIMIT :limit
                """), params)
                
                products = [dict(row) for row in result]
                app_logger.info(f"RAG检索到 {len(products)} 个相似商品")
                return products
                
        except Exception as e:
            app_logger.error(f"RAG检索失败: {e}")
            return []
    
    async def search_by_text_only(
        self, 
        query_text: str,
        filters: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """仅基于文本的向量搜索"""
        
        try:
            text_vector = await self.embedding_service.embed_text(query_text)
            
            where_conditions = ["vector_status = 3"]
            params = {
                'text_vector': json.dumps(text_vector),
                'limit': limit
            }
            
            # 添加筛选条件
            if 'scene' in filters and filters['scene']:
                where_conditions.append("scene = :scene")
                params['scene'] = filters['scene']
            
            where_clause = " AND ".join(where_conditions)
            
            with next(get_db()) as db:
                result = db.execute(text(f"""
                    SELECT *, 
                           text_vector <-> :text_vector AS distance
                    FROM product_vectors 
                    WHERE {where_clause}
                    ORDER BY text_vector <-> :text_vector
                    LIMIT :limit
                """), params)
                
                return [dict(row) for row in result]
                
        except Exception as e:
            app_logger.error(f"文本向量搜索失败: {e}")
            return []
```

### 第二步：修改推荐智能体

修改 `app/services/recommendation_agent.py`：

```python
# 在 RecommendationAgent 类中添加RAG服务
class RecommendationAgent:
    def __init__(self, model_client: QwenVLClient):
        self.model_client = model_client
        self.rag_service = RAGService()  # 新增RAG服务
        # ... 其他初始化代码
    
    async def process(self, request: UserRequest, memory: Optional[Memory] = None) -> Dict[str, Any]:
        """处理用户请求"""
        try:
            # 验证请求
            if not request.image:
                return {"error": "请提供单品图片", "agent_type": "recommendation"}
            
            if not request.prompt:
                return {"error": "请提供搭配提示词", "agent_type": "recommendation"}
            
            # 检查是否需要询问预算和风格偏好
            if not request.budget or not request.style:
                missing_info = []
                if not request.budget:
                    missing_info.append("预算")
                if not request.style:
                    missing_info.append("风格偏好")
                
                return {
                    "agent_type": "recommendation",
                    "needs_more_info": True,
                    "missing_info": missing_info,
                    "message": f"为了给您提供更精准的搭配推荐，请告诉我您的{' 和 '.join(missing_info)}。",
                    "style_options": ["sports", "casual"]
                }
            
            # RAG检索相关商品
            similar_products = await self.rag_service.search_similar_products(
                query_text=request.prompt,
                query_image=request.image.image_url,
                filters={
                    'scene': request.style,
                    'max_price': request.budget * 1.2  # 允许20%的价格浮动
                },
                limit=10
            )
            
            # 构建增强提示词
            prompt = self._build_rag_prompt(request, similar_products, memory)
            
            # 调用模型生成推荐
            image_data = {"image_url": request.image.image_url}
            response = await self.model_client.generate(
                prompt=prompt,
                image=image_data,
                temperature=0.7,
                max_tokens=1024
            )
            
            # 解析推荐结果
            result = self._parse_recommendation_result(response)
            
            return {
                "agent_type": "recommendation",
                "result": {
                    "recommendations": [
                        {
                            "item_type": item.item_type,
                            "description": item.description,
                            "style": item.style,
                            "price_range": item.price_range,
                            "matching_reason": item.matching_reason
                        } for item in result.recommendations
                    ],
                    "reasoning": result.reasoning
                }
            }
            
        except Exception as e:
            app_logger.error(f"单品推荐失败: {e}")
            return {"error": f"单品推荐失败: {e}", "agent_type": "recommendation"}
    
    def _build_rag_prompt(self, request: UserRequest, similar_products: List[Dict], memory: Optional[Memory] = None) -> str:
        """构建包含RAG检索结果的推荐提示词"""
        
        # 格式化检索到的商品信息
        products_context = ""
        if similar_products:
            products_context = "\n\n相关商品信息（基于向量相似性搜索）：\n"
            for i, product in enumerate(similar_products[:5], 1):
                products_context += f"""
商品{i}：
- 名称：{product.get('product_name', '')}
- 品牌：{product.get('brand', '')}
- 价格：{product.get('price', 0)}元
- 风格：{product.get('style', '')}
- 颜色：{product.get('color', '')}
- 场景：{product.get('scene', '')}
- 描述：{product.get('description', '')}
- 相似度：{product.get('text_distance', 0):.3f}
"""
        
        # 基础提示词
        prompt = """
你是一位专业的时尚搭配顾问，需要根据用户上传的单品图片和提示词，推荐匹配的单品。

请先分析用户上传的是上装还是下装，然后根据用户的提示词、预算范围和风格偏好，推荐3-5件匹配的单品。

请按照以下格式回复：

```json
{
  "recommendations": [
    {
      "item_type": "上装/下装",
      "description": "详细描述",
      "style": "风格类型",
      "price_range": "价格范围",
      "matching_reason": "匹配理由"
    }
  ],
  "reasoning": "整体搭配理念和建议"
}
```

请确保推荐的单品与用户上传的单品在风格、颜色、场合等方面协调匹配，并考虑用户的预算和风格偏好。
"""
        
        # 添加用户信息
        prompt += f"\n\n用户提示词: {request.prompt}"
        
        if request.budget:
            prompt += f"\n预算范围: {request.budget}元"
        
        if request.style:
            style_display = "运动" if request.style == "sports" else "休闲"
            prompt += f"\n风格偏好: {style_display}"
        
        # 添加RAG检索结果
        prompt += products_context
        
        # 添加历史记忆
        if memory and memory.interactions:
            previous_recommendations = [
                interaction for interaction in memory.interactions 
                if interaction.agent_type == "recommendation"
            ]
            
            if previous_recommendations:
                prompt += "\n\n用户之前的推荐历史："
                for i, interaction in enumerate(previous_recommendations[-2:], 1):
                    prompt += f"\n历史推荐{i}: 用户曾对{interaction.request.get('prompt', '未知单品')}进行搭配查询"
        
        return prompt
```

### 第三步：确保数据库索引

根据指南，确保创建了必要的索引：

```sql
-- 在数据库中执行以下SQL
-- 1. 基础索引
CREATE INDEX IF NOT EXISTS idx_product_vectors_scene ON product_vectors(scene);
CREATE INDEX IF NOT EXISTS idx_product_vectors_color ON product_vectors(color);
CREATE INDEX IF NOT EXISTS idx_product_vectors_style ON product_vectors(style);
CREATE INDEX IF NOT EXISTS idx_product_vectors_price ON product_vectors(price);

-- 2. 向量索引（如果使用pgvector）
CREATE INDEX IF NOT EXISTS idx_product_vectors_text_vector ON product_vectors 
USING ivfflat (text_vector vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_product_vectors_image_vector ON product_vectors 
USING ivfflat (image_vector vector_cosine_ops) WITH (lists = 100);
```

### 第四步：测试RAG功能

创建测试脚本 `test_rag.py`：

```python
import asyncio
from app.services.rag_service import RAGService

async def test_rag():
    rag_service = RAGService()
    
    # 测试文本+图片搜索
    results = await rag_service.search_similar_products(
        query_text="休闲风格的白色T恤",
        query_image="https://example.com/white-tshirt.jpg",
        filters={
            'scene': 'casual',
            'max_price': 500
        },
        limit=5
    )
    
    print(f"找到 {len(results)} 个相似商品")
    for product in results:
        print(f"- {product['product_name']} ({product['brand']}) - ¥{product['price']}")

if __name__ == "__main__":
    asyncio.run(test_rag())
```

### 第五步：运行测试

```bash
# 1. 确保数据库中有向量数据
python run_vectorization.py

# 2. 测试RAG检索
python test_rag.py

# 3. 启动应用测试完整流程
python run.py
```

## 关键实现要点

1. **严格按照指南的SQL查询格式**：使用 `text_vector <-> :query_vector` 进行向量相似性搜索
2. **混合搜索策略**：先按标签筛选，再按向量相似性排序
3. **错误处理**：完善的异常处理和日志记录
4. **性能优化**：使用索引和LIMIT限制结果数量
5. **上下文注入**：将检索结果格式化后注入到提示词中

这样实现后，你的推荐智能体就能基于真实的商品数据进行RAG推荐了！
