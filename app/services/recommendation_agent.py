from typing import Dict, Any, Optional, List
from app.core.logging import app_logger
from app.models.memory import Memory, UserRequest, RecommendationResult, RecommendationItem
from app.services.model_client import QwenVLClient
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text, and_, or_, func, join
from app.models.database import get_db, SessionLocal
from app.services.vectorization.embedding_service import AliyunEmbeddingService
from app.models.product_vectors import ProductVectors
from app.models.categories import Category


class RAGService:
    """RAG检索服务，实现向量相似性搜索"""
    
    def __init__(self):
        self.embedding_service = AliyunEmbeddingService()
    
    async def search_similar_products(
        self, 
        query_text: str, 
        query_image: str,
        filters: Dict[str, Any],
        limit: int = 5,
        exclude_category_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """混合搜索：标签筛选 + 向量相似性 + 类别过滤"""
        
        try:
            # 1. 向量化查询
            text_vector = await self.embedding_service.embed_text(query_text)
            image_vector = await self.embedding_service.embed_image(query_image)
            
            # 2. 构建查询条件
            conditions = [ProductVectors.vector_status == 3]  # 只查询已完成的向量
            
            # 添加标签筛选条件
            if 'scene' in filters and filters['scene']:
                conditions.append(ProductVectors.scene == filters['scene'])
            
            if 'color' in filters and filters['color']:
                conditions.append(ProductVectors.color == filters['color'])
            
            if 'style' in filters and filters['style']:
                conditions.append(ProductVectors.style == filters['style'])
            
            if 'max_price' in filters and filters['max_price']:
                conditions.append(ProductVectors.price <= filters['max_price'])
            
            # 3. 使用SQLAlchemy ORM执行混合搜索
            with SessionLocal() as session:
                # 基础查询
                query = session.query(
                    ProductVectors,
                    (ProductVectors.text_vector.l2_distance(text_vector)).label('text_similarity'),
                    (ProductVectors.image_vector.l2_distance(image_vector)).label('image_similarity')
                ).filter(and_(*conditions))
                
                # 添加类别过滤条件
                if exclude_category_type:
                    # 根据要排除的类别类型确定要保留的parent_id
                    if exclude_category_type == "上装":
                        # 排除上装，保留下装（parent_id=24）
                        target_parent_id = 23
                    elif exclude_category_type == "下装":
                        # 排除下装，保留上装（parent_id=23）
                        target_parent_id = 24
                    else:
                        target_parent_id = None
                    
                    if target_parent_id:
                        # 添加与categories表的join和过滤条件
                        query = query.join(
                            Category, 
                            ProductVectors.category_id == Category.id
                        ).filter(Category.parent_id == target_parent_id)
                
                # 按相似度排序
                query = query.order_by(
                    'text_similarity', 
                    'image_similarity'
                ).limit(limit)
                
                results = query.all()
                
                products = []
                for result in results:
                    product_dict = result[0].to_dict()
                    product_dict['text_similarity'] = float(result[1]) if result[1] is not None else None
                    product_dict['image_similarity'] = float(result[2]) if result[2] is not None else None
                    products.append(product_dict)
                
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
            
            if 'color' in filters and filters['color']:
                where_conditions.append("color = :color")
                params['color'] = filters['color']
            
            if 'max_price' in filters and filters['max_price']:
                where_conditions.append("price <= :max_price")
                params['max_price'] = filters['max_price']
            
            where_clause = " AND ".join(where_conditions)
            
            with next(get_db()) as db:
                app_logger.info(f"执行RAG文本搜索，查询条件: {where_clause}")
                app_logger.info(f"搜索参数: {params}")
                
                result = db.execute(text(f"""
                    SELECT *, 
                           text_vector <-> :text_vector AS distance
                    FROM product_vectors 
                    WHERE {where_clause}
                    ORDER BY text_vector <-> :text_vector
                    LIMIT :limit
                """), params)
                
                # 安全地转换结果
                products = []
                row_count = 0
                for row in result:
                    row_count += 1
                    try:
                        # 将SQLAlchemy Row对象转换为字典
                        row_dict = {}
                        for key, value in row._mapping.items():
                            row_dict[key] = value
                        products.append(row_dict)
                        app_logger.debug(f"成功转换第{row_count}行数据")
                    except Exception as e:
                        app_logger.warning(f"转换第{row_count}行数据失败: {e}, 跳过该行")
                        continue
                
                app_logger.info(f"RAG文本搜索完成，共处理{row_count}行，成功转换{len(products)}个商品")
                return products
                
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
            # 验证请求：要么有图片+提示词，要么有文本描述
            if not request.image and not request.text:
                return {
                    "error": "请提供单品图片或描述您想要的单品",
                    "agent_type": "recommendation"
                }
            
            # 如果是纯文本推荐，验证文本是否包含具体的单品描述
            if not request.image and request.text:
                # 检查文本是否包含具体的单品描述关键词（基于数据库分类）
                clothing_keywords = [
                    # 上装类别
                    "上衣", "上装",  # 添加通用上装关键词
                    "针织毛衫", "毛衣", "毛衫", "针织衫",
                    "T恤", "t恤", "polo", "POLO", "polo衫",
                    "衬衫", "衬衣", "白衬衫",
                    "连衣裙", "长裙", "连身裙",
                    "风衣", "长风衣",
                    "卫衣", "连帽衫", "帽衫",
                    "皮革", "皮衣", "皮夹克",
                    "背心", "吊带", "背心/吊带",
                    "夹克", "外套", "夹克/外套",
                    "大衣", "长外套", "风衣大衣",
                    "棉服", "羽绒服", "棉服/羽绒服",
                    "内衣", "泳衣", "内衣/泳衣",
                    "家居服", "睡衣",
                    "礼服", "旗袍", "礼服/旗袍",
                    "套装", "西装套装",
                    "西装", "西装凸甲",
                    # 下装类别
                    "下装", "下衣",  # 添加通用下装关键词
                    "牛仔", "牛仔裤",
                    "长裤", "裤子", "西裤", "休闲裤",
                    "短裤", "热裤",
                    "半身裙", "短裙", "裙装"
                ]
                text_lower = request.text.lower()
                has_clothing_keyword = any(keyword in text_lower for keyword in clothing_keywords)
                
                if not has_clothing_keyword:
                    return {
                        "error": "请描述您想要的具体单品，例如：推荐一件白色T恤、我要买一条牛仔裤、找件风衣等",
                        "agent_type": "recommendation"
                    }
            
            # 验证图片URL是否有效
            if request.image and request.image.image_url:
                # 检查图片URL是否有效（不是空字符串、'string'等无效值）
                if (not request.image.image_url or 
                    request.image.image_url.strip() == '' or 
                    request.image.image_url == 'string' or
                    not request.image.image_url.startswith(('http://', 'https://'))):
                    app_logger.warning(f"无效的图片URL: {request.image.image_url}")
                    return {
                        "error": "请提供有效的单品图片URL",
                        "agent_type": "recommendation"
                    }
                
            # 如果有图片但没有提示词，使用文本作为提示词
            if request.image and not request.prompt:
                request.prompt = request.text or "请推荐匹配的单品"
                
            # 如果没有图片但有文本，使用文本作为提示词进行纯文本推荐
            if not request.image and request.text:
                request.prompt = request.text
            
            # 检查是否需要询问预算和风格偏好
            missing_info = []
            
            # 首先尝试从提示词中提取风格信息
            if not request.style:
                if "运动" in request.prompt or "sports" in request.prompt.lower():
                    request.style = "sports"
                elif "休闲" in request.prompt or "casual" in request.prompt.lower():
                    request.style = "casual"
            
            # 检查预算
            if not request.budget:
                missing_info.append("预算")
            
            # 检查风格
            if not request.style or request.style not in ["sports", "casual"]:
                missing_info.append("风格偏好")
                request.style = None  # 重置无效的风格值
            
            # 如果有缺失信息，返回询问信息
            if missing_info:
                # 检查是否已经询问过相同的信息
                if memory and memory.interactions:
                    last_interaction = memory.interactions[-1]
                    if (last_interaction.agent_type == "recommendation" and 
                        last_interaction.response.get("needs_more_info", False)):
                        # 如果上次已经询问过相同的信息，直接进行推荐
                        app_logger.warning(f"用户未提供完整信息，但已询问过相同缺失信息: {missing_info}")
                        request.style = request.style or "casual"  # 设置默认风格
                        request.budget = request.budget or 500  # 设置默认预算
                    else:
                        # 否则返回询问信息
                        return {
                            "agent_type": "recommendation",
                            "needs_more_info": True,
                            "missing_info": missing_info,
                            "message": f"为了给您提供更精准的搭配推荐，请告诉我您的{' 和 '.join(missing_info)}。",
                            "style_options": ["sports", "casual"]  # 只支持运动和休闲两种风格
                        }
                else:
                    # 如果没有记忆，返回询问信息
                    return {
                        "agent_type": "recommendation",
                        "needs_more_info": True,
                        "missing_info": missing_info,
                        "message": f"为了给您提供更精准的搭配推荐，请告诉我您的{' 和 '.join(missing_info)}。",
                        "style_options": ["sports", "casual"]  # 只支持运动和休闲两种风格
                    }
            
            # 确保风格值为有效选项
            if request.style and request.style not in ["sports", "casual"]:
                request.style = "casual"  # 默认使用休闲风格
                
            # 确保风格值为有效选项
            if request.style and request.style not in ["sports", "casual"]:
                request.style = "casual"  # 默认使用休闲风格
                
            # 确定用户想要的服装类型
            if request.image:
                # 有图片时，分析图片类型
                clothing_type = await self._analyze_clothing_type(request.image.image_url, request.prompt)
                # RAG检索相关商品，排除相同类型的服装
                similar_products = await self.rag_service.search_similar_products(
                    query_text=request.prompt,
                    query_image=request.image.image_url,
                    filters={
                        'scene': request.style,
                        'max_price': request.budget * 1.2  # 允许20%的价格浮动
                    },
                    limit=10,
                    exclude_category_type=clothing_type
                )
            else:
                # 纯文本推荐，分析文本确定服装类型和颜色
                clothing_type = await self._analyze_clothing_type_from_text(request.prompt)
                extracted_color = self._extract_color_from_text(request.prompt)
                
                # 构建搜索过滤器
                search_filters = {
                    'scene': request.style,
                    'max_price': request.budget * 1.2  # 允许20%的价格浮动
                }
                
                # 如果提取到颜色信息，添加到过滤器中
                if extracted_color:
                    search_filters['color'] = extracted_color
                
                app_logger.info(f"纯文本推荐 - 服装类型: {clothing_type}, 提取颜色: {extracted_color}")
                app_logger.info(f"纯文本推荐 - 搜索过滤器: {search_filters}")
                app_logger.info(f"纯文本推荐 - 查询文本: {request.prompt}")
                
                # 使用纯文本RAG搜索
                similar_products = await self.rag_service.search_by_text_only(
                    query_text=request.prompt,
                    filters=search_filters,
                    limit=10
                )
                
                app_logger.info(f"纯文本推荐 - RAG搜索结果数量: {len(similar_products)}")
            
            # 构建增强提示词，包含RAG检索结果
            prompt = self._build_rag_prompt(request, similar_products, memory)
            
            # 调用模型生成匹配理由
            image_data = None
            if request.image:
                image_data = {
                    "image_url": request.image.image_url
                }
            
            response = await self.model_client.generate(
                prompt=prompt,
                image=image_data,
                temperature=0.7,
                max_tokens=1024
            )
            
            # 解析推荐结果获取匹配理由
            result = self._parse_recommendation_result(response)
            
            # 使用RAG检索结果构建推荐列表，但使用模型生成的匹配理由
            recommendations = []
            for i, product in enumerate(similar_products[:5]):  # 取前5个最相似的商品
                # 使用模型生成的匹配理由，如果没有则使用默认理由
                matching_reason = result.recommendations[i].matching_reason if i < len(result.recommendations) else f"与您的查询相似度: {product.get('text_similarity', 0):.3f}"
                
                recommendation = {
                    "product_id": product.get("product_id", ""),
                    "product_name": product.get("product_name", ""),
                    "description": product.get("description", ""),
                    "image_gif": product.get("image_gif", ""),
                    "category_id": product.get("category_id", ""),
                    "brand": product.get("brand", ""),
                    "price": product.get("price", 0),
                    "scene": product.get("scene", ""),
                    "matching_reason": matching_reason
                }
                recommendations.append(recommendation)
            
            # 生成自然语言描述
            # 生成自然语言描述
            text_output = f"{result.reasoning}\n"
            
            for idx, product in enumerate(recommendations[:5], 1):
                text_output += f"## {idx}. {product['product_name']}\n"
                text_output += f"**商品id**: {product['product_id']}\n"
                text_output += f"**商品名字**: {product['product_name']}\n"
                text_output += f"**描述**: {product['description']}\n"
                # text_output += f"**商品类别**: {product['category_id']}\n"
                text_output += f"**品牌**: {product['brand']}\n"
                text_output += f"**价格**: {product['price']}\n"
                text_output += f"**风格类型**: {product['scene']}\n"
                text_output += f"**推荐理由**: {product['matching_reason']}\n"
                if product.get('image_gif'):
                    text_output += f"![商品图片]({product['image_gif']})\n"                

            return {
                "agent_type": "recommendation",
                "result": {
                    "recommendations": recommendations,
                    "reasoning": result.reasoning,
                    "text": text_output  # 新增自然语言描述
                }
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

    async def _analyze_clothing_type(self, image_url: str, prompt: str) -> str:
        """分析服装类型（上装/下装）
        
        Args:
            image_url: 图片URL
            prompt: 用户提示词
            
        Returns:
            "上装" 或 "下装"
        """
        # 直接调用模型分析图片和文本
        analysis_prompt = (
            "你是分辨用户需要什么互补搭配的专家，擅长结合用户提示词和图片分析需要的服装类型。"
            "具体来说，如果用户给出上装图片，或提示词里提到了他有上装，或提示词里提到了他需要搭配下装，你需要推荐下装；如果用户给出下装图片，或提示词里提到了他有下装，或提示词里提到了他需要搭配上装，你需要推荐上装。"
            f"用户提示词: {prompt}"
            "图片中的服装类型是: [图片分析]"
            "请只回答'上装'或'下装'"
        )
        
        app_logger.info(f"开始分析服装类型，图片URL: {image_url}, 提示词: {prompt}")
        
        response = await self.model_client.generate(
            prompt=analysis_prompt,
            image={"image_url": image_url},
            max_tokens=10
        )
        result = self.model_client.extract_text_from_response(response)
        
        clothing_type = "上装" if "上装" in result else "下装"
        app_logger.info(f"服装类型分析结果: {clothing_type}, 模型原始输出: {result}")
        
        return clothing_type

    async def _analyze_clothing_type_from_text(self, text: str) -> str:
        """从文本中分析用户想要的服装类型（上装/下装）
        
        Args:
            text: 用户文本描述
            
        Returns:
            "上装" 或 "下装"
        """
        # 基于数据库中的分类数据匹配服装类型
        # 上装类别 (parent_id = 23)
        upper_keywords = [
            "上衣", "上装",  # 添加通用上装关键词
            "针织毛衫", "毛衣", "毛衫", "针织衫",
            "T恤", "t恤", "polo", "POLO", "polo衫",
            "衬衫", "衬衣", "白衬衫",
            "连衣裙", "长裙", "连身裙",
            "风衣", "长风衣",
            "卫衣", "连帽衫", "帽衫",
            "皮革", "皮衣", "皮夹克",
            "背心", "吊带", "背心/吊带",
            "夹克", "外套", "夹克/外套",
            "大衣", "长外套", "风衣大衣",
            "棉服", "羽绒服", "棉服/羽绒服",
            "内衣", "泳衣", "内衣/泳衣",
            "家居服", "睡衣",
            "礼服", "旗袍", "礼服/旗袍",
            "套装", "西装套装",
            "西装", "西装凸甲"
        ]
        
        # 下装类别 (parent_id = 24)
        lower_keywords = [
            "下装", "下衣",  # 添加通用下装关键词
            "牛仔", "牛仔裤",
            "长裤", "裤子", "西裤", "休闲裤",
            "短裤", "热裤",
            "半身裙", "短裙", "裙装"
        ]
        
        text_lower = text.lower()
        
        for keyword in upper_keywords:
            if keyword in text_lower:
                app_logger.info(f"从文本中识别到上装关键词: {keyword}")
                return "上装"
        
        for keyword in lower_keywords:
            if keyword in text_lower:
                app_logger.info(f"从文本中识别到下装关键词: {keyword}")
                return "下装"
        
        # 如果无法确定，默认返回上装（因为用户通常更容易描述上衣）
        app_logger.info("无法从文本中确定服装类型，默认返回上装")
        return "上装"
    
    def _extract_color_from_text(self, text: str) -> Optional[str]:
        """从文本中提取颜色信息
        
        Args:
            text: 用户文本描述
            
        Returns:
            颜色字符串或None
        """
        # 基于数据库中的颜色数据映射
        color_keywords = {
            "黑色": ["黑色", "黑", "纯黑", "深黑"],
            "白色": ["白色", "白", "纯白", "雪白"],
            "红色": ["红色", "红", "大红", "深红", "鲜红"],
            "蓝色": ["蓝色", "蓝", "深蓝", "浅蓝", "天蓝", "宝蓝"],
            "绿色": ["绿色", "绿", "深绿", "浅绿", "草绿"],
            "黄色": ["黄色", "黄", "深黄", "浅黄", "金黄"],
            "紫色": ["紫色", "紫", "深紫", "浅紫", "薰衣草紫"],
            "灰色": ["灰色", "灰", "深灰", "浅灰", "银灰"],
            "粉色": ["粉色", "粉", "深粉", "浅粉", "玫瑰粉"],
            "米色": ["米色", "米白", "浅米", "奶白"],
            "卡其色": ["卡其色", "卡其", "土黄", "驼色"]
        }
        
        text_lower = text.lower()
        
        for color, keywords in color_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    app_logger.info(f"从文本中识别到颜色: {color}")
                    return color
        
        return None

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
        if request.image:
            prompt = """
你是一位专业的时尚搭配顾问，需要根据用户上传的单品图片和提示词，推荐匹配的单品。

请先分析用户上传的是上装还是下装，然后根据用户的提示词、预算范围和风格偏好，推荐3-5件匹配的单品。
"""
        else:
            prompt = """
你是一位专业的时尚搭配顾问，需要根据用户的文本描述，推荐匹配的单品。

请根据用户的描述、预算范围和风格偏好，推荐3-5件匹配的单品。
"""

        prompt += """
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

请确保推荐的单品符合用户的描述和需求，在风格、颜色、场合等方面协调匹配，并考虑用户的预算和风格偏好。
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