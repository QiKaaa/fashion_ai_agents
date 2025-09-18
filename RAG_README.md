# RAG 说明（基于当前项目实现）

本说明文档聚焦于本项目的 RAG（Retrieval-Augmented Generation，检索增强生成）实现：当前的多模态相似检索、上下文构建、以及在推荐 Agent 中的使用方式，并提供环境配置、运行与测试方法，以及常见问题排查。

## 架构概览
- **多模态向量化**：
  - 文本向量：`app/services/vectorization/embedding_service.py` 中的 `AliyunEmbeddingService.embed_text`。
  - 图片向量：`AliyunEmbeddingService.embed_image`（需确保按你的阿里云接口正确实现返回与文本同维度的向量）。
- **向量存储**：
  - 目标表：`product_vectors`（参考 `data/vectors/create_unified_table.sql`）。
  - 写入流程：`app/services/vectorization/vector_storage_service.py` 的 `VectorStorageService.store_product_vectors`，将商品文本与图片生成向量并入库。
- **检索服务（RAGService）**：
  - 位置：`app/services/recommendation_agent.py` 内部类 `RAGService`。
  - 能力：文本-only 检索与文本+图片混合检索；支持结构化条件过滤（如 `scene`）。
  - 度量：使用 pgvector 风格 `<->` 距离；混合检索按 `(text_distance + image_distance)/2` 排序。
- **上下文增强**：
  - 位置：`RecommendationAgent._build_rag_prompt`。
  - 将检索到的商品（名称、品牌、价格、风格、颜色、场景、描述、距离）以要点形式拼接进模型提示词。
- **生成模型**：
  - `app/services/model_client.py` 的 `QwenVLClient` 调用 Qwen-VL-Plus 进行多模态生成。

## 数据流（端到端）
1. 用户在 `/api/v1/chat` 发送文本与可选图片 URL（在推荐场景）。
2. `WorkflowManager` 将请求路由到 `RecommendationAgent`。
3. `RecommendationAgent` 调用内嵌 `RAGService`：
   - 对查询文本与图片分别向量化。
   - 在 `product_vectors` 中执行向量相似检索（可加 `scene` 等过滤）。
4. 将前 N 个相似商品转为结构化上下文，拼入提示词。
5. `QwenVLClient` 调用大模型生成推荐结果。
6. 解析模型输出为结构化 `RecommendationResult`，返回给 API。

## 依赖与环境变量
见 `app/core/config.py`，关键项：
- 基础服务
  - `REDIS_HOST`/`REDIS_PORT`/`REDIS_DB`/`REDIS_PASSWORD`：会话记忆必需；应用启动即连接。
  - `POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`：RAG 检索阶段需要。
- 模型与向量
  - `QWEN_API_KEY`、`QWEN_API_BASE_URL`：调用 Qwen-VL-Plus。
  - `ALIYUN_API_KEY`、`ALIYUN_EMBEDDING_ENDPOINT`、`ALIYUN_EMBEDDING_MODEL`：文本/图片向量化。
  - `EMBEDDING_DIMENSION`、`MAX_RETRIES`：向量化配置。
- API 运行
  - `API_HOST`、`API_PORT`、`DEBUG`。

建议创建 `.env`（示例）：
```
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=True

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Postgres + pgvector
echo '需要你本地创建扩展: CREATE EXTENSION IF NOT EXISTS vector;'
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=fashion_ai

# Qwen 模型
QWEN_API_KEY=YOUR_QWEN_KEY
QWEN_API_BASE_URL=https://api.qwen.ai/v1

# 阿里云 Embedding（按你实际接口填写）
ALIYUN_API_KEY=YOUR_ALIYUN_KEY
ALIYUN_EMBEDDING_ENDPOINT=https://dashscope.aliyuncs.com
ALIYUN_EMBEDDING_MODEL=multimodal-embedding-v1

EMBEDDING_DIMENSION=1024
MAX_RETRIES=3
```

## 数据库与向量准备
1. 安装并启用 `pgvector`：
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
2. 创建/更新 `product_vectors` 表：
   - 参考 `data/vectors/create_unified_table.sql` 执行。
3. 注入向量数据：
   - 如果已有 `products` 源表，可编写脚本遍历商品并调用 `VectorStorageService.store_product_vectors`。
   - `store_product_vectors` 会：
     - 将 `product_name + description` 拼接为文本内容；
     - 调用 `embed_text` 与 `embed_image` 生成向量；
     - 插入或更新 `product_vectors` 记录（包含结构化字段与原始数据）。

## 启动与验证
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 启动 Redis（示例用 Docker）：
   ```bash
   docker run --name fashion-redis -p 6379:6379 -d redis:7-alpine
   ```
3. 确保 PostgreSQL、`product_vectors` 表与向量数据准备完毕。
4. 运行服务：
   ```bash
   python run.py
   ```
5. 健康检查：
   ```bash
   curl http://127.0.0.1:8000/api/v1/health
   ```

## 触发 RAG 的 API 示例
- 创建会话：
  ```bash
  curl -X POST http://127.0.0.1:8000/api/v1/sessions -H 'Content-Type: application/json' -d '{}'
  ```
  记录 `data.session_id`。

- 发起推荐（文本+图片，触发 RAG）：
  ```bash
  curl -X POST http://127.0.0.1:8000/api/v1/chat \
    -H 'Content-Type: application/json' \
    -d '{
      "session_id": "<SESSION_ID>",
      "text": "这条黑色运动裤适合配什么上衣？预算300-500元",
      "image": {"image_url": "https://your-cdn.com/path/to/pants.jpg"},
      "style": "sports",
      "budget": 500
    }'
  ```

- 普通问答（不依赖 RAG）：
  ```bash
  curl -X POST http://127.0.0.1:8000/api/v1/chat \
    -H 'Content-Type: application/json' \
    -d '{
      "session_id": "<SESSION_ID>",
      "text": "给我一些休闲风的搭配建议"
    }'
  ```

## 重要实现细节与注意事项
- 距离与相似度：
  - 代码展示字段为 `text_distance`/`image_distance`，值越小越相似；展示时如需“相似度”，可转换为 `1/(1+d)` 或归一化分数。
- 加权策略：
  - 混合检索当前使用 `(text_distance + image_distance)/2`，可按业务需要引入权重并调参。
- 模态缺失：
  - 当仅有文本或仅有图片时，应只使用可用模态的向量参与排序，避免零向量干扰（可在 `RAGService` 内做自适应）。
- 性能建议：
  - 为 `product_vectors` 的向量列建立合适的 pgvector 索引（如 `ivfflat`/`hnsw`），并选择合适的 `probes` 参数以兼顾速度与召回。
- 健壮性：
  - `AliyunEmbeddingService` 的请求体需与实际阿里云接口一致；建议为向量化与检索增加超时与重试；
  - `_build_rag_prompt` 中“相似度”展示源自距离，注意命名与用户认知一致性。

## 常见问题排查
- 应用启动时报 Redis 连接失败：
  - 确认本地 6379 端口可用，或调整 `REDIS_HOST/PORT`。
- `/chat` 调用返回模型鉴权错误：
  - 检查 `QWEN_API_KEY` 是否配置，或代理地址 `QWEN_API_BASE_URL` 是否可达。
- 检索为空或报错：
  - 检查 PostgreSQL 连接参数；确认 `product_vectors` 有数据；检查 pgvector 扩展与索引；
  - 确认 `embed_text`/`embed_image` 维度一致且与表定义一致。

---
如需，我可以提供：
- 一个最小化的向量注入脚本，读取样例商品并批量写入 `product_vectors`；
- 将混合排序改为可配置权重的编辑；
- 将距离转相似度并在提示中展示更直观的分值。 