from typing import Dict, List, Optional, Any
from app.core.logging import app_logger
from app.models.memory import Memory, UserRequest
from app.services.model_client import QwenVLClient
import re


class IntentRecognizer:
    """意图识别服务，用于分析用户输入并识别用户意图"""
    
    def __init__(self, model_client: QwenVLClient):
        """初始化意图识别服务
        
        Args:
            model_client: 模型客户端
        """
        self.model_client = model_client
        # 定义意图类型
        self.intent_types = ["scoring", "recommendation", "default"]
    
    async def recognize(self, request: UserRequest, memory: Optional[Memory] = None) -> str:
        """识别用户意图
        
        Args:
            request: 用户请求
            memory: 会话记忆
            
        Returns:
            意图类型: "scoring", "recommendation", "default"
        """
        try:
            # 首先从自然语言中提取预算和风格信息
            if request.text and (not request.budget or not request.style):
                extracted_info = await self._extract_budget_and_style(request.text)
                
                # 如果用户没有明确指定预算，但我们从文本中提取到了，则更新请求
                if not request.budget and "budget" in extracted_info:
                    request.budget = extracted_info["budget"]
                    app_logger.info(f"从文本中提取到预算: {request.budget}")
                
                # 如果用户没有明确指定风格，但我们从文本中提取到了，则更新请求
                if not request.style and "style" in extracted_info:
                    request.style = extracted_info["style"]
                    app_logger.info(f"从文本中提取到风格: {request.style}")
            
            # 构建提示词
            prompt = self._build_prompt(request, memory)
            
            # 调用模型进行意图识别
            image_data = None
            if request.image:
                image_data = {
                    "image_url": request.image.image_url
                }
            
            response = await self.model_client.generate(
                prompt=prompt,
                image=image_data,
                temperature=0.3,  # 使用较低的温度以获得更确定的结果
                max_tokens=100  # 意图识别只需要较短的回复
            )
            
            # 解析模型响应，提取意图
            intent = self._parse_intent(response)
            app_logger.info(f"识别到的意图: {intent}")
            
            return intent
            
        except Exception as e:
            app_logger.error(f"意图识别失败: {e}")
            # 出错时返回默认意图
            return "default"
    
    def _build_prompt(self, request: UserRequest, memory: Optional[Memory] = None) -> str:
        """构建意图识别提示词
        
        Args:
            request: 用户请求
            memory: 会话记忆
            
        Returns:
            提示词
        """
        # 基础提示词
        prompt = """
你是一个意图识别助手，需要根据用户的输入判断用户的意图类型。可能的意图类型有：

1. scoring（试衣评分）：用户提供了穿搭图片，希望对穿搭进行评分和建议。\
2. recommendation（单品推荐）：用户提供了单品图片（上装或下装）和提示词，希望推荐匹配的单品。\
3. default（一般问题）：用户询问与时尚相关的一般性问题。\

请分析用户输入，并只返回一个意图类型（scoring、recommendation或default）。\

--
这里是一些常见的用户输入的例子，能帮助你更好地进行意图识别：\

+ 用户输入：我想要试穿这件衣服，你觉得怎么样？ 意图类型：scoring\

+ 用户输入：这件衣服好看吗？ 意图类型：scoring\

+ 用户输入：我想要买一件上衣，有什么推荐的？ 意图类型：recommendation\

+ 用户输入：你可以干什么？ 意图类型：default\

--
现在，根据以下信息，判断用户的意图类型（只返回scoring、recommendation或default中的一个）：\
用户输入：\
"""
        
        # 添加用户文本输入
        if request.text:
            prompt += f"\n文本: {request.text}"
        
        # 添加图片信息
        if request.image:
            prompt += "\n图片: [用户上传了一张图片]"
        
        # 添加提示词信息
        if request.prompt:
            prompt += f"\n提示词: {request.prompt}"
            
        # 添加预算信息
        if request.budget:
            prompt += f"\n预算: {request.budget}"
            
        # 添加风格偏好信息
        if request.style:
            prompt += f"\n风格偏好: {request.style}"
        
        # 添加历史记忆信息
        if memory and memory.interactions:
            prompt += "\n\n用户之前的交互历史："
            # 最多添加最近3次交互
            recent_interactions = memory.interactions[-3:] if len(memory.interactions) > 3 else memory.interactions
            for i, interaction in enumerate(recent_interactions):
                prompt += f"\n交互{i+1} - 类型: {interaction.agent_type}"
                if "text" in interaction.request:
                    prompt += f", 用户输入: {interaction.request.get('text', '')}"
        
        prompt += "\n\n请根据以上信息，判断用户的意图类型（只返回scoring、recommendation或default中的一个）："
        
        return prompt
    
    async def _extract_budget_and_style(self, text: str) -> Dict[str, Any]:
        """从用户文本中提取预算和风格信息
        
        Args:
            text: 用户文本
            
        Returns:
            包含预算和风格信息的字典
        """
        result = {}
        
        try:
            # 1. 使用规则匹配提取预算信息
            # 匹配类似"预算500元"、"价格在300-500之间"、"300块以内"等表达
            budget_patterns = [
                r'预算[约在是]?(\d+)[-到至]?(\d+)?[块元]?',
                r'(\d+)[-到至]?(\d+)?[块元][以]?[内下]',
                r'[不低少]于(\d+)[块元]',
                r'[不超过高于多于](\d+)[块元]',
                r'(\d+)[块元][左右上下]?'
            ]
            
            for pattern in budget_patterns:
                match = re.search(pattern, text)
                if match:
                    # 如果匹配到范围(如300-500)
                    if match.group(2):
                        # 取范围的中间值
                        min_val = float(match.group(1))
                        max_val = float(match.group(2))
                        budget = (min_val + max_val) / 2
                    else:
                        # 单一数值
                        budget = float(match.group(1))
                    
                    result["budget"] = budget
                    break
            
            # 2. 使用规则匹配提取风格信息 - 只支持运动(sports)和休闲(casual)两种风格
            style_keywords = {
                "sports": ["运动", "健身", "活力", "跑步", "篮球", "足球", "户外", "体育", "动感", "训练"],
                "casual": ["休闲", "舒适", "日常", "宽松", "简单", "随意", "自在", "轻松", "悠闲"]
            }
            
            # 遍历风格关键词，检查是否在文本中出现
            for style, keywords in style_keywords.items():
                for keyword in keywords:
                    if keyword in text:
                        result["style"] = style
                        break
                if "style" in result:
                    break
            
            # 3. 如果规则匹配失败，可以使用模型进行提取
            # 这部分可以在后续版本中实现，使用模型进行更复杂的语义理解
            
            return result
            
        except Exception as e:
            app_logger.error(f"提取预算和风格信息失败: {e}")
            return {}
    
    def _parse_intent(self, response: Dict[str, Any]) -> str:
        """解析模型响应，提取意图类型
        
        Args:
            response: 模型响应
            
        Returns:
            意图类型: "scoring", "recommendation", "default"
        """
        try:
            # 从模型响应中提取文本
            text = self.model_client.extract_text_from_response(response)
            
            # 转换为小写并去除空白字符
            text = text.lower().strip()
            
            # 检查文本中是否包含意图类型关键词
            if "scoring" in text:
                return "scoring"
            elif "recommendation" in text:
                return "recommendation"
            else:
                return "default"
                
        except Exception as e:
            app_logger.error(f"解析意图失败: {e}")
            return "default"
