# AI试衣多智能体系统 API 参考文档

## 概述

本文档提供了AI试衣多智能体系统的API接口说明。系统包含三个主要智能体：试衣评分、单品推荐和默认智能体，通过意图识别自动路由用户请求到合适的智能体。

## 基础URL

```
http://<host>:<port>/api/v1
```

## 统一响应格式

所有API响应均遵循以下统一格式：

```json
{
  "code": 200,       // 状态码，200表示成功，其他值表示错误
  "message": "success", // 响应消息
  "data": {}         // 响应数据，根据不同接口返回不同的数据结构
}
```

## 会话管理

### 创建会话

创建一个新的会话，用于跟踪用户交互历史。

**请求**

```
POST /sessions
```

**请求体**

```json
{
  "user_id": "string" // 可选，用户ID
}
```

**响应**

```json
{
  "code": 200,
  "message": "会话创建成功",
  "data": {
    "session_id": "string" // 会话ID，用于后续请求
  }
}
```

### 结束会话

结束一个会话，清除相关记忆数据。

**请求**

```
DELETE /sessions/{session_id}
```

**响应**

```json
{
  "code": 200,
  "message": "会话已结束",
  "data": {
    "session_id": "string"
  }
}
```

## 智能体交互

### 聊天接口

与智能体系统进行交互，系统会自动识别意图并路由到合适的智能体。

**请求**

```
POST /chat
```

**请求体**

```json
{
  "session_id": "string", // 会话ID
  "text": "string", // 可选，用户文本输入
  "image": { // 可选，图片数据
    "image_url": "string" // 图片URL/base64，用于Qwen-VL-Plus模型
  },
  "prompt": "string", // 可选，用于单品推荐的提示词
  "budget": 0, // 可选，预算范围
  "style": "string" // 可选，服装风格偏好（sports/casual）
}
```


**响应**

```json
{
  "code": 200,
  "message": "处理成功",
  "data": {
    "agent_type": "string", // "scoring", "recommendation", "default"
    "result": {}, // 根据agent_type不同，返回不同的结果结构
    "needs_more_info": false, // 可选，是否需要更多信息
    "missing_info": [], // 可选，缺失的信息类型列表
    "message": "string" // 可选，提示信息
  }
}
```

#### 试衣评分结果结构

当`agent_type`为`"scoring"`时，`result`的结构如下：

```json
{
  "overall_score": 8.5, // 总体评分
  "dimension_scores": { // 各维度评分
    "整体协调性": 8,
    "色彩搭配": 9,
    "风格一致性": 8,
    "场合适宜性": 8,
    "个人气质匹配度": 9
  },
  "comments": "这是一套非常协调的穿搭...", // 评价内容
  "suggestions": [ // 改进建议
    "建议1...",
    "建议2...",
    "建议3..."
  ]
}
```

#### 单品推荐结果结构

当`agent_type`为`"recommendation"`时，`result`的结构如下：

```json
{
  "recommendations": [ // 推荐单品列表
    {
      "product_id": "商品ID", // 商品唯一标识
      "product_name": "商品名称", // 商品名称
      "description": "商品描述", // 商品详细描述
      "image_gif": "商品图片URL", // 商品图片地址
      "category_id": "分类ID", // 商品分类标识
      "brand": "品牌名称", // 商品品牌
      "price": 199.99, // 商品价格
      "scene": "风格类型", // 适用场景/风格
      "matching_reason": "匹配理由" // AI生成的匹配理由
    }
  ],
  "reasoning": "整体搭配理念和建议" // 推荐理由
}
```

#### 默认回答结果结构

当`agent_type`为`"default"`时，`result`的结构如下：

```json
{
  "answer": "详细的回答内容...", // 回答内容
  "sources": [ // 信息来源
    "信息来源1",
    "信息来源2"
  ]
}
```

#### 需要更多信息的响应

当系统需要用户提供更多信息时，响应中会包含以下字段：

```json
{
  "code": 200,
  "message": "需要更多信息",
  "data": {
    "agent_type": "recommendation",
    "needs_more_info": true,
    "missing_info": ["budget", "style"], // 缺失的信息类型
    "message": "为了给您提供更准确的搭配推荐，请提供以下信息：\n- 您的预算是多少？\n- 您偏好哪种风格？(运动/休闲)",
    "style_options": ["sports", "casual"] // 可选的风格选项
  }
}
```

## 健康检查

### 健康状态

检查API服务的健康状态。

**请求**

```
GET /health
```

**响应**

```json
{
  "code": 200,
  "message": "服务正常",
  "data": {
    "status": "ok",
    "version": "1.0.0"
  }
}
```

## 错误处理

所有API错误响应也遵循统一的响应格式：

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

常见HTTP状态码：

- 200: 成功
- 400: 请求参数错误
- 404: 资源不存在
- 500: 服务器内部错误

## 图片处理说明

**重要更新**：系统现在使用Qwen-VL-Plus模型处理图像，该模型要求通过image_url传递图片，而不是使用Base64编码和MIME类型。

### 图片URL要求

- 图片URL必须是可公开访问的URL
- 支持的图片格式：JPEG、PNG、WebP
- 建议图片分辨率：不低于800x800像素，不超过4096x4096像素
- 建议图片文件大小：不超过10MB

### 示例

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "这套衣服搭配得怎么样？",
  "image": {
    "image_url": "https://example.com/images/outfit.jpg"
  }
}