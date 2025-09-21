# AI试衣多智能体系统使用指南

本指南提供了AI试衣多智能体系统的基本使用方法，特别是关于API响应格式、图片处理和单品推荐功能的最新更新。

## 系统概述

AI试衣多智能体系统是一个基于LangGraph的多智能体系统，包含三个主要智能体：

1. **试衣评分智能体**：评估用户穿搭并提供专业评分和建议
2. **单品推荐智能体**：根据用户上传的单品图片推荐匹配的搭配
3. **默认智能体**：回答用户关于时尚和穿搭的一般性问题

系统会自动识别用户意图，并将请求路由到最合适的智能体处理。

## 重要更新

### API响应格式统一

所有API响应现在遵循统一的RESTful格式：

```json
{
  "code": 200,       // 状态码，200表示成功，其他值表示错误
  "message": "success", // 响应消息
  "data": {}         // 响应数据，根据不同接口返回不同的数据结构
}
```

### 图片处理方式变更

系统现在使用Qwen-VL-Plus模型处理图像，该模型要求通过image_url传递图片，而不是使用Base64编码和MIME类型。

**旧方式（不再支持）**：
```json
{
  "image": {
    "content": "base64_encoded_image_content",
    "mime_type": "image/jpeg"
  }
}
```

**新方式**：
```json
{
  "image": {
    "image_url": "https://example.com/images/outfit.jpg"
  }
}
```

### 单品推荐风格限制

单品推荐功能现在仅支持两种风格：
- 运动风格（sports）
- 休闲风格（casual）

系统会在需要时主动询问用户的预算和风格偏好。

### 类别过滤机制

系统具备智能类别过滤功能，确保推荐逻辑合理：
- **互补推荐**：自动识别输入单品的类型（上装/下装），确保推荐不同类别的单品
- **避免重复**：不会推荐与输入单品相同类型的衣服
- **类型识别**：基于商品分类体系（上装parent_id=23，下装parent_id=24）

### 会话验证机制

系统提供完整的会话状态管理：
- **会话创建**：每个会话有唯一session_id，有效期1小时
- **会话验证**：所有操作前都会验证会话是否存在
- **会话删除**：删除后立即失效，无法继续使用
- **状态检查**：实时验证会话状态，确保数据一致性

## 基本使用流程

### 1. 创建会话

首先需要创建一个会话，获取session_id：

```bash
curl -X POST "http://localhost:8000/api/v1/sessions" \
     -H "Content-Type: application/json" \
     -d '{}'
```

响应示例：
```json
{
  "code": 200,
  "message": "会话创建成功",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### 2. 试衣评分

上传穿搭图片获取专业评分：

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "session_id": "550e8400-e29b-41d4-a716-446655440000",
           "text": "这套衣服搭配得怎么样？",
           "image": {
             "image_url": "https://example.com/images/outfit.jpg"
           }
         }'
```

响应示例：
```json
{
  "code": 200,
  "message": "处理成功",
  "data": {
    "agent_type": "scoring",
    "result": {
      "overall_score": 8.5,
      "dimension_scores": {
        "整体协调性": 8,
        "色彩搭配": 9,
        "风格一致性": 8,
        "场合适宜性": 8,
        "个人气质匹配度": 9
      },
      "comments": "这是一套非常协调的穿搭...",
      "suggestions": [
        "建议1...",
        "建议2...",
        "建议3..."
      ]
    }
  }
}
```

### 3. 单品推荐

上传单品图片获取搭配推荐：

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "session_id": "550e8400-e29b-41d4-a716-446655440000",
           "text": "帮我搭配一下这件上衣",
           "image": {
             "image_url": "https://example.com/images/top.jpg"
           },
           "prompt": "休闲风格的搭配",
           "budget": 500,
           "style": "casual"
         }'
```

如果缺少预算或风格信息，系统会返回询问：

```json
{
  "code": 200,
  "message": "需要更多信息",
  "data": {
    "agent_type": "recommendation",
    "needs_more_info": true,
    "missing_info": ["budget", "style"],
    "message": "为了给您提供更准确的搭配推荐，请提供以下信息：\n- 您的预算是多少？\n- 您偏好哪种风格？(运动/休闲)",
    "style_options": ["sports", "casual"]
  }
}
```

然后，您可以提供缺失的信息：

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "session_id": "550e8400-e29b-41d4-a716-446655440000",
           "text": "我的预算是300元，喜欢运动风格",
           "image": {
             "image_url": "https://example.com/images/top.jpg"
           },
           "prompt": "休闲风格的搭配",
           "budget": 300,
           "style": "sports"
         }'
```

单品推荐响应示例：
```json
{
  "code": 200,
  "message": "处理成功",
  "data": {
    "agent_type": "recommendation",
    "result": {
      "recommendations": [
        {
          "product_id": "1001",
          "product_name": "运动休闲T恤",
          "description": "纯棉材质，透气舒适，适合运动休闲场合",
          "image_gif": "https://example.com/images/tshirt.jpg",
          "category_id": "201",
          "brand": "运动品牌",
          "price": 199.99,
          "scene": "sports",
          "matching_reason": "这款T恤与您的上衣风格匹配，采用透气面料，适合运动场合"
        },
        {
          "product_id": "1002",
          "product_name": "休闲运动裤",
          "description": "弹性面料，活动自如，适合日常运动和休闲穿着",
          "image_gif": "https://example.com/images/pants.jpg",
          "category_id": "202",
          "brand": "休闲品牌",
          "price": 299.99,
          "scene": "casual",
          "matching_reason": "这条裤子与您的上衣颜色协调，剪裁合身，适合休闲场合"
        }
      ],
      "reasoning": "基于您的运动风格偏好和300元预算，为您推荐了2件匹配的单品，注重功能性和舒适度"
    }
  }
}
```

### 4. 时尚问答

询问一般性时尚问题：

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "session_id": "550e8400-e29b-41d4-a716-446655440000",
           "text": "什么颜色的衣服适合春季穿？"
         }'
```

响应示例：
```json
{
  "code": 200,
  "message": "处理成功",
  "data": {
    "agent_type": "default",
    "result": {
      "answer": "春季适合穿着明亮、柔和的颜色...",
      "sources": [
        "时尚指南2025",
        "春季色彩搭配手册"
      ]
    }
  }
}
```

### 5. 结束会话

完成交互后结束会话：

```bash
curl -X DELETE "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000"
```

响应示例：
```json
{
  "code": 200,
  "message": "会话已结束",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

## 错误处理

当发生错误时，API会返回统一格式的错误响应：

```json
{
  "code": 400, // 错误状态码
  "message": "请求处理失败", // 简短错误消息
  "data": {
    "code": 400, // 错误码
    "message": "请求参数验证失败", // 详细错误消息
    "details": "具体错误详情" // 可选，更详细的错误信息
  }
}
```

常见错误状态码：
- 400: 请求参数错误
- 404: 资源不存在（如无效的session_id）
- 500: 服务器内部错误

## 图片URL最佳实践

为了获得最佳效果，请确保：

1. 图片URL必须是可公开访问的
2. 图片清晰可见，主体突出
3. 图片分辨率适中（建议800x800至4096x4096像素）
4. 文件大小不超过10MB
5. 使用常见图片格式（JPEG、PNG、WebP）

## 常见问题

### Q: 为什么系统不接受我的图片？
A: 请确保您提供的是有效的图片URL，而不是Base64编码的图片内容。URL必须是可公开访问的。

### Q: 为什么我无法选择其他风格？
A: 目前系统仅支持运动(sports)和休闲(casual)两种风格，以提供更精准的推荐。

### Q: 会话会保存多久？
A: 会话默认保存1小时，超时后会自动清除。

### Q: 如何获取最准确的评分和推荐？
A: 上传清晰、完整的图片，并提供详细的文本描述和偏好信息。

### Q: 如何处理API错误？
A: 检查返回的错误码和错误消息，根据提示修正请求参数或联系系统管理员。

## 更多资源

- [API参考文档](api_reference.md)
- [项目GitHub仓库](https://github.com/yourusername/fashion_ai_agents)