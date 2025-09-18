# AI试衣多Agent智能体系统

基于LangGraph构建的多智能体系统，用于AI试衣场景，包括试衣评分、单品推荐和时尚问答功能。

## 项目概述

本项目是一个基于LangGraph的多智能体系统，使用Qwen-VL-Plus模型处理多模态输入，通过FastAPI提供RESTful API接口。系统能够根据用户输入自动识别意图，并将请求路由到最合适的专业智能体处理，同时保持会话记忆功能。

### 核心功能

1. **意图识别与智能路由**：系统能够分析用户输入，自动识别用户意图，并将请求路由到最合适的专业智能体。
2. **试衣评分智能体**：接收用户上传的穿搭图片，进行多维度专业评分，提供穿搭建议。
3. **单品推荐智能体**：根据用户上传的上装/下装图片和提示词，推荐最匹配的下装/上装，实现智能搭配推荐。支持两种场景：运动(sports)和休闲(casual)。
4. **默认智能体**：处理其他类型的用户问题，从预设文档库中检索最相关的信息进行回答。
5. **会话记忆功能**：在单个会话中保持上下文记忆，使对话更加连贯自然。
6. **交互式信息收集**：当用户请求单品推荐但缺少预算或风格信息时，系统会主动询问这些信息，提供更精准的推荐。

## 技术架构

- **框架**：LangGraph + FastAPI
- **模型**：Qwen-VL-Plus
- **数据存储**：Redis + PostgreSQL + pgvector
- **工具库**：Langchain + Uvicorn

## 数据字段说明

### 场景字段 (scene)

- **casual**: 休闲场景，适用于日常穿着
- **sports**: 运动场景，适用于运动健身

### 其他RAG筛选字段

- **color**: 颜色（如：黑色、白色、红色等）
- **style**: 风格（如：休闲、运动、正式等）
- **fit**: 版型（如：宽松、修身、合身等）
- **material**: 材质（如：棉、涤纶、牛仔等）
- **season**: 季节（如：春、夏、秋、冬、all）
- **pattern**: 图案（如：纯色、条纹、印花等）

## 目录结构

```
fashion_ai_agents/
├── app/
│   ├── api/              # API接口
│   ├── core/             # 核心配置
│   ├── models/           # 数据模型
│   ├── services/         # 服务实现
│   └── utils/            # 工具函数
├── logs/                 # 日志文件
├── .env.example          # 环境变量示例
├── requirements.txt      # 依赖包
├── run.py                # 启动脚本
└── README.md             # 项目说明
```

## 安装与配置

### 前置条件

- Python 3.8+
- Redis
- PostgreSQL (with pgvector extension)

### 安装步骤

1. 克隆项目

```bash
git clone https://github.com/yourusername/fashion_ai_agents.git
cd fashion_ai_agents
```

2. 创建并激活虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 配置环境变量

```bash
cp .env.example .env
# 编辑.env文件，填入必要的配置信息
```

5. 启动应用

```bash
python run.py
```

## API接口

系统提供RESTful API接口，所有API响应均遵循统一的格式：

```json
{
  "code": 200,       // 状态码，200表示成功，其他值表示错误
  "message": "success", // 响应消息
  "data": {}         // 响应数据，根据不同接口返回不同的数据结构
}
```

### 会话管理

- `POST /api/v1/sessions`：创建新会话
- `DELETE /api/v1/sessions/{session_id}`：结束会话

### 智能体交互

- `POST /api/v1/chat`：与智能体系统交互

### 健康检查

- `GET /api/v1/health`：检查系统健康状态

## 使用示例

### 创建会话

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

### 发送聊天请求

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "session_id": "your_session_id",
           "text": "这套衣服搭配得好看吗？",
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

## 图片处理说明

**重要更新**：系统现在使用Qwen-VL-Plus模型处理图像，该模型要求通过image_url传递图片，而不是使用Base64编码和MIME类型。

### 图片URL要求

- 图片URL必须是可公开访问的URL
- 支持的图片格式：JPEG、PNG、WebP
- 建议图片分辨率：不低于800x800像素，不超过4096x4096像素
- 建议图片文件大小：不超过10MB

## 注意事项

- 需要有效的Qwen-VL-Plus API密钥
- 会话有效期默认为1小时
- 单品推荐功能仅支持运动(sports)和休闲(casual)两种风格

## 文档

- [API参考文档](docs/api_reference.md)
- [使用指南](docs/usage_guide.md)

## 许可证

[MIT License](LICENSE)
