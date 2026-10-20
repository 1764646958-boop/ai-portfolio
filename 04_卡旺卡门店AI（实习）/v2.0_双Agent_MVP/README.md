# 门店声音洞察 Agent — MVP

基于《MVP开发指南_门店声音Agent_CodePrompts.md》实现的门店声音洞察 Agent。

## 快速开始

### 前置条件
- Python 3.12+
- Node.js 18+（前端）

### 1. 安装依赖
```bash
pip install -r requirements.txt
pip install aiosqlite
```

### 2. 配置 LLM API Key（可选，不填则跳过 LLM 环节）
编辑 `.env`：
```
LLM_API_KEY=sk-xxxx    # 填入你的 Deepseek API Key
```

### 3. 启动后端
```bash
cd D:\work\MVP
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. 启动前端（可选）
```bash
cd D:\work\MVP\frontend
npm install
npm run dev
```

### 5. 测试 API
```bash
# 健康检查
curl http://localhost:8000/health

# 录入店员反馈
curl -X POST http://localhost:8000/feedback/ingest \
  -H "Content-Type: application/json" \
  -d '{"store_id":"HF001","staff_id":"STF001","content":"桂花酒酿太甜了","input_method":"text"}'

# 获取信号
curl "http://localhost:8000/signals?period=this_week"
```

## 架构说明

```
S00(文本清洗) → S01(标签匹配) → S02(信号检测) → S03(双源融合) → S04(建议卡)
```

## ⚠️ [计划外] 环境适配说明

当前开发环境（Windows，网络受限）无法使用 Docker、PostgreSQL、Milvus、BGE 模型，已做以下适配：

| 组件 | 原设计 | 当前实现 | 说明 |
|------|--------|---------|------|
| 数据库 | PostgreSQL | **SQLite**（自动回退） | Docker 不可用，asyncpg 接口保持 |
| 向量库 | Milvus | **内存检索**（自动回退） | 14 个标签 brute-force 匹配 |
| Embedding | BGE-large-zh | **哈希嵌入**（自动回退） | 网络无法下载模型 |
| LLM | Deepseek | Deepseek（需 API Key） | API Key 未填时自动降级 |

**切换到完整方案（Docker + PostgreSQL + Milvus + BGE）**：
1. 安装 Docker Desktop
2. `docker compose up -d`
3. 修改 `.env` 中 `USE_HASH_EMBEDDING=0`
4. 重启后端，代码会自动检测并切换到完整方案

## 项目结构

```
app/
├── main.py              # FastAPI 入口
├── config.py            # 配置
├── infrastructure/
│   ├── postgres.py      # PostgreSQL 连接池（自动回退 SQLite）
│   ├── postgres_fallback.py  # ⚠️ SQLite 回退
│   ├── embedding.py     # BGE 单例（自动回退哈希）
│   ├── embedding_fallback.py # ⚠️ 哈希嵌入
│   ├── milvus_init.py   # Milvus 初始化（自动回退内存）
│   └── milvus_fallback.py    # ⚠️ 内存检索
├── agents/store_voice/
│   ├── s00_text_ingest.py
│   ├── s01_knowledge_enhance.py
│   ├── s02_signal_detect.py
│   ├── s03_fusion.py
│   └── s04_opportunity_card.py
├── orchestration/store_voice_graph.py
└── api/routes.py

scripts/
├── import_data.py       # 数据导入（Excel 拆分 + 清洗）
└── field_mapping.yaml

data/
└── feedbacks.csv        # ⚠️ 30 条模拟店员反馈

tests/
└── test_store_voice_l1_l4.py  # L1-L4 分层测试

frontend/
└── src/                 # Vue 3 前端
```

## 测试

```bash
pytest tests/test_store_voice_l1_l4.py -v
```
