import httpx
import json
import asyncio
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import app_logger


class AliyunEmbeddingService:
    """阿里云多模态embedding服务"""
    
    def __init__(self):
        self.api_key = settings.ALIYUN_API_KEY
        self.endpoint = settings.ALIYUN_EMBEDDING_ENDPOINT
        self.model = settings.ALIYUN_EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.max_retries = settings.MAX_RETRIES
        
        if not self.api_key:
            app_logger.warning("阿里云API Key未配置，请检查环境变量ALIYUN_API_KEY")
    
    async def embed_text(self, text: str) -> List[float]:
        """文本向量化
        
        Args:
            text: 输入文本
            
        Returns:
            文本向量
        """
        try:
            data = {
                "model": "multimodal-embedding-v1",
                "input": {
                    "contents": [
                        {"text": text}
                    ]
                },
                "parameters": {}
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.endpoint}/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # 查找text类型的embedding
                    for embedding in result["output"]["embeddings"]:
                        if embedding["type"] == "text":
                            return embedding["embedding"]
                    # 如果没有找到text类型，返回第一个
                    return result["output"]["embeddings"][0]["embedding"]
                else:
                    app_logger.error(f"文本向量化失败: {response.status_code}, {response.text}")
                    return self._get_zero_vector()
                    
        except Exception as e:
            app_logger.error(f"文本向量化异常: {e}")
            return self._get_zero_vector()
    
    async def embed_image(self, image_url: str) -> List[float]:
        """图片向量化
        
        Args:
            image_url: 图片URL
            
        Returns:
            图片向量
        """
        try:
            data = {
                "model": "multimodal-embedding-v1",
                "input": {
                    "contents": [
                        {"image": image_url}
                    ]
                },
                "parameters": {}
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.endpoint}/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # 查找image类型的embedding
                    for embedding in result["output"]["embeddings"]:
                        if embedding["type"] == "image":
                            return embedding["embedding"]
                    # 如果没有找到image类型，返回第一个
                    return result["output"]["embeddings"][0]["embedding"]
                else:
                    app_logger.error(f"图片向量化失败: {response.status_code}, {response.text}")
                    return self._get_zero_vector()
                    
        except Exception as e:
            app_logger.error(f"图片向量化异常: {e}")
            return self._get_zero_vector()
    
    async def embed_multimodal(self, contents: List[Dict[str, str]]) -> List[List[float]]:
        """多模态向量化（批量处理文本和图片）
        
        Args:
            contents: 内容列表，格式为 [{"text": "文本内容"}, {"image": "图片URL"}]
            
        Returns:
            向量列表，按输入顺序返回
        """
        try:
            data = {
                "model": "multimodal-embedding-v1",
                "input": {
                    "contents": contents
                },
                "parameters": {}
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.endpoint}/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json=data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # 按index顺序返回embeddings
                    embeddings = [None] * len(contents)
                    for embedding in result["output"]["embeddings"]:
                        embeddings[embedding["index"]] = embedding["embedding"]
                    return embeddings
                else:
                    app_logger.error(f"多模态向量化失败: {response.status_code}, {response.text}")
                    return [self._get_zero_vector()] * len(contents)
                    
        except Exception as e:
            app_logger.error(f"多模态向量化异常: {e}")
            return [self._get_zero_vector()] * len(contents)
    
    def _get_zero_vector(self) -> List[float]:
        """获取零向量（用于错误处理）"""
        return [0.0] * self.dimension
