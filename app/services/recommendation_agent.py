from typing import Dict, Any, Optional, List
from app.core.logging import app_logger
from app.models.memory import Memory, UserRequest, RecommendationResult, RecommendationItem
from app.services.model_client import QwenVLClient
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from app.models.database import get_db
from app.services.vectorization.embedding_service import AliyunEmbeddingService


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


class RecommendationAgent:
    """单品推荐Agent，用于根据用户上传的单品图片和提示词推荐匹配的单品"""
    
    def __init__(self, model_client: QwenVLClient):
        """初始化单品推荐Agent
        
        Args:
            model_client: 模型客户端
        """
        self.model_client = model_client
        self.rag_service = RAGService()  # 新增RAG服务
        # 定义服装类型
        self.clothing_types = ["上装", "下装"]
        # 定义风格类型
        self.style_types = ["运动", "休闲", "正式", "商务", "街头", "复古", "优雅", "简约"]
    
    async def process(self, request: UserRequest, memory: Optional[Memory] = None) -> Dict[str, Any]:
        """处理用户请求
        
        Args:
            request: 用户请求
            memory: 会话记忆
            
        Returns:
            推荐结果
        """
        try:
            # 验证请求中是否包含图片
            if not request.image:
                return {
                    "error": "请提供单品图片",
                    "agent_type": "recommendation"
                }
                
            # 验证请求中是否包含提示词
            if not request.prompt:
                return {
                    "error": "请提供搭配提示词",
                    "agent_type": "recommendation"
                }
            
            # 检查是否需要询问预算和风格偏好
            if not request.budget or not request.style:
                # 如果缺少预算或风格信息，返回询问信息
                missing_info = []
                if not request.budget:
                    missing_info.append("预算")
                if not request.style:
                    missing_info.append("风格偏好")
                
                return {
                    "agent_type": "recommendation",
                    "need_more_info": True,
                    "missing_info": missing_info,
                    "message": f"为了给您提供更精准的搭配推荐，请告诉我您的{' 和 '.join(missing_info)}。",
                    "style_options": ["sports", "casual"]  # 只支持运动和休闲两种风格
                }
                
            # 确保风格值为有效选项
            if request.style and request.style not in ["sports", "casual"]:
                request.style = "casual"  # 默认使用休闲风格
                
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
            
            # 调用模型进行推荐
            image_data = {
                "image_url": request.image.image_url
            }
            
            response = await self.model_client.generate(
                prompt=prompt,
                image=image_data,
                temperature=0.7,
                max_tokens=1024
            )
            
            # 解析推荐结果
            result = self._parse_recommendation_result(response)
            
            # 将 RecommendationResult 对象转换为字典
            result_dict = {
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
            
            return {
                "agent_type": "recommendation",
                "result": result_dict
            }
            
        except Exception as e:
            app_logger.error(f"单品推荐失败: {e}")
            return {
                "error": f"单品推荐失败: {e}",
                "agent_type": "recommendation"
            }
    
    def _build_recommendation_prompt(self, request: UserRequest, memory: Optional[Memory] = None) -> str:
        """构建推荐提示词
        
        Args:
            request: 用户请求
            memory: 会话记忆
            
        Returns:
            提示词
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
    },
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
        
        # 添加用户提示词
        prompt += f"\n\n用户提示词: {request.prompt}"
        
        # 添加预算信息
        if request.budget:
            # 根据预算范围提供更具体的指导
            if request.budget < 200:
                prompt += f"\n预算范围: {request.budget}元 (经济实惠价位)"
            elif request.budget < 500:
                prompt += f"\n预算范围: {request.budget}元 (中等价位)"
            elif request.budget < 1000:
                prompt += f"\n预算范围: {request.budget}元 (中高价位)"
            else:
                prompt += f"\n预算范围: {request.budget}元 (高端价位)"
                
            # 添加预算限制指导
            prompt += "\n请确保推荐的单品价格符合用户预算，可以适当推荐一些略高和略低于预算的选项，但不要超出太多。"
        else:
            prompt += "\n预算范围: 未指定，请推荐不同价位的选项"
            
        # 添加风格偏好信息
        if request.style:
            # 只支持两种风格：运动(sports)和休闲(casual)
            style_guidance = {
                "sports": "运动风格：注重功能性和舒适度，选择透气面料和活动自如的剪裁，适合运动和活跃场景",
                "casual": "休闲风格：强调舒适与日常实用，选择易于搭配的基础款，适合日常穿着和轻松场合"
            }
            
            style_display = "运动" if request.style == "sports" else "休闲"
            prompt += f"\n风格偏好: {style_display}"
            if request.style in style_guidance:
                prompt += f" - {style_guidance[request.style]}"
        else:
            prompt += "\n风格偏好: 未指定，请根据用户上传的单品风格进行匹配，优先考虑运动和休闲风格"
        
        # 添加用户文本输入（如果有）
        if request.text:
            prompt += f"\n\n用户说: {request.text}"
            
        # 添加历史记忆信息（如果有）
        if memory and memory.interactions:
            # 查找之前的推荐记录，了解用户的喜好
            previous_recommendations = [
                interaction for interaction in memory.interactions 
                if interaction.agent_type == "recommendation"
            ]
            
            if previous_recommendations:
                prompt += "\n\n用户之前的推荐历史："
                for i, interaction in enumerate(previous_recommendations[-2:]):  # 最多显示最近2次
                    prompt += f"\n历史推荐{i+1}: 用户曾对{interaction.request.get('prompt', '未知单品')}进行搭配查询"
        
        return prompt
    
    def _parse_recommendation_result(self, response: Dict[str, Any]) -> RecommendationResult:
        """解析推荐结果
        
        Args:
            response: 模型响应
            
        Returns:
            推荐结果
        """
        try:
            # 从模型响应中提取文本
            text = self.model_client.extract_text_from_response(response)
            
            # 尝试从文本中提取JSON
            import re
            import json
            
            # 使用正则表达式提取JSON部分
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                # 处理可能的控制字符
                json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
                try:
                    result_dict = json.loads(json_str)
                except json.JSONDecodeError as e:
                    app_logger.error(f"JSON解析错误: {e}, 原始字符串: {json_str}")
                    default_item = RecommendationItem(
                        item_type="未知",
                        description=f"解析推荐结果失败: 无效的JSON格式，请稍后重试。",
                        style="未知",
                        price_range="未知",
                        matching_reason="请稍后重试"
                    )
                    return RecommendationResult(
                        recommendations=[default_item],
                        reasoning="解析推荐结果失败: 无效的JSON格式，请稍后重试。"
                    )
                
                # 创建推荐项列表
                recommendations = []
                for item_dict in result_dict.get("recommendations", []):
                    recommendation_item = RecommendationItem(
                        item_type=item_dict.get("item_type", ""),
                        description=item_dict.get("description", ""),
                        style=item_dict.get("style", ""),
                        price_range=item_dict.get("price_range", ""),
                        matching_reason=item_dict.get("matching_reason", "")
                    )
                    recommendations.append(recommendation_item)
                
                # 创建RecommendationResult对象
                result = RecommendationResult(
                    recommendations=recommendations,
                    reasoning=result_dict.get("reasoning", "")
                )
                
                return result
            else:
                # 如果无法提取JSON，创建默认结果
                app_logger.warning("无法从模型响应中提取JSON，使用默认结果")
                default_item = RecommendationItem(
                    item_type="未知",
                    description="无法解析推荐结果",
                    style="未知",
                    price_range="未知",
                    matching_reason="请重试"
                )
                return RecommendationResult(
                    recommendations=[default_item],
                    reasoning="无法解析推荐结果，请重试。"
                )
                
        except Exception as e:
            app_logger.error(f"解析推荐结果失败: {e}")
            # 出错时返回默认结果
            default_item = RecommendationItem(
                item_type="未知",
                description=f"解析推荐结果失败: {e}",
                style="未知",
                price_range="未知",
                matching_reason="请稍后重试"
            )
            return RecommendationResult(
                recommendations=[default_item],
                reasoning=f"解析推荐结果失败: {e}"
            )

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