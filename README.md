# AI Agentic RAG 企业知识库平台

> 一套完整的企业级 RAG（检索增强生成）知识库系统：文档入库 → 混合检索 → 流式问答 → Agentic 推理 → 自动化评测，全链路可在 Docker 中一键部署运行。

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6F61)](https://langchain-ai.github.io/langgraph/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Tests](https://img.shields.io/badge/tests-143%2F143-brightgreen)](#-测试)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> ▶ **[在线体验（交互式演示）](https://youligit.github.io/enterprise-knowledge-base/demo/)** —— 无需部署，直接在浏览器中回放真实的检索管线与 Agentic 问答过程（含 6 阶段量纲追踪、逐字流式输出、引用来源）。也可以直接打开仓库内的 [`demo/index.html`](demo/index.html)。

---

## ⚠️ 安全警告（部署前必读）

本项目为**教学 / 演示 / 二次开发**用途，为降低上手门槛，数据库密码与 JWT 密钥以**明文默认值**写在 `docker-compose.yml` 与 `fastapi-app/settings.py` 中：

| 项目 | 默认值 | 位置 |
|---|---|---|
| MySQL / PostgreSQL 密码 | `root123456` | `docker-compose.yml` |
| JWT 签名密钥 | `ai-system-secret-please-change` | `docker-compose.yml` |
| 管理员账号 | `admin` / `admin` | 首次启动自动创建 |

**若用于生产环境，务必在上线前修改以下内容：**

1. 修改 `docker-compose.yml` 中所有 `*_PASSWORD` 与 `JWT_SECRET` 为强随机值
2. 修改管理员默认密码（登录后 → 个人资料 → 修改密码）
3. 不要将暴露到公网的实例直接使用默认凭据
4. 建议改为通过 `.env` 文件或环境变量外部注入，避免密钥进入版本库

> 本项目仅供学习与内部使用，因使用默认凭据造成的安全风险由使用者自行承担。

---

## 📖 目录

- [项目简介](#-项目简介)
- [核心特性](#-核心特性)
- [技术栈](#-技术栈)
- [系统架构](#-系统架构)
- [检索管线](#-检索管线)
- [目录结构](#-目录结构)
- [快速开始](#-快速开始)
- [零成本体验（Mock 沙箱）](#-零成本体验mock-大模型沙箱)
- [使用指南](#-使用指南)
- [测试](#-测试)
- [配置说明](#-配置说明)
- [常见问题排查](#-常见问题排查)
- [接口概览](#-接口概览)
- [设计约定](#-设计约定)
- [已知限制](#-已知限制)

---

## 🎯 项目简介

本系统面向企业内部的**非结构化文档知识管理**场景：把 PDF / Word / Excel / Markdown / TXT 等资料采集入库，通过**混合检索 + 重排**找到最相关的内容，再由大模型生成**可溯源、可引用**的答案；同时提供 **Agentic RAG**（让模型自主判断检索结果是否充分、不足则改写查询重试）与 **LLM-as-judge 自动化评测**，用于量化评估检索与生成质量。

**解决的典型问题：**

| 痛点 | 本系统的做法 |
|---|---|
| 纯向量检索对专业术语、型号、编号不敏感 | 向量 + BM25 双通道召回，RRF 名次融合 |
| 检索回来的是零碎小块，模型读不全 | 父子分块：**小块用来找，大块用来答** |
| 召回后排序不精准 | 接入重排模型（gte-rerank-v2）二次精排 |
| 模型答案容易编造、无法溯源 | Prompt 强制标注出处编号，答案与引用一同落库 |
| 检索一次不够准，人工反复试 | Agentic RAG：自动评估召回充分性并改写重试 |
| 效果好坏全凭感觉 | 四指标自动评测（Recall / Precision / Faithfulness / Relevancy） |
| 各阶段分数口径混乱、无法解释 | **StageTrace 量纲显式化**，每阶段标注打分口径与阈值适用性 |

---

## ✨ 核心特性

### 检索与知识库
- **混合检索管线**：查询改写 → 向量召回 ∥ BM25 召回 → RRF 融合 → 父块回填 → 重排
- **父子分块策略**：父块（大块）用于生成答案，子块（小块）用于向量检索，兼顾召回精度与上下文完整性
- **多种查询改写**：多查询扩展（multi_query）、指代消解（coref）、HyDE 假设文档
- **量纲显式化 StageTrace**：每阶段标注打分口径（cosine / bm25 / rrf / rerank）与**阈值是否适用**，全程可回放、可解释
- **召回调试台**：多套检索策略并排对比，直观看到差异

### 问答与 Agent
- **SSE 真流式问答**：逐 token 推送，前端逐字打字效果，附引用来源表格
- **Agentic RAG 状态图**（LangGraph）：`retrieve → evaluate →（不足则 rewrite → retrieve）→ generate → self_check`
- **Function Calling 工具中心**：内置计算器、当前时间、知识库检索三个工具，模型按需自主调用
- **Agent 运行时间线**：每个节点的思考、输入输出、耗时全部落库，支持回放

### 评测与运营
- **LLM-as-judge 四指标**：Context Recall / Context Precision / Faithfulness / Answer Relevancy
- **Context Recall 不依赖模型**：基于 `source_chunk_ids` 集合运算，结果确定可复现
- **策略对比看板**：多套检索策略跑同一评测集，产出综合分对比
- **反馈闭环**：答案点赞 / 点踩，踩过的问题计入首页「待优化」统计

### 工程化
- **统一返回契约**：所有接口 `{code, msg, data}`，业务异常统一 `HTTP 200 + code ≠ 0`
- **模型配置热更新**：模型配置存 MySQL，改完即生效（2 秒 TTL 缓存）
- **可离线测试**：内置 Mock 大模型沙箱，无付费 Key 也能跑通全链路
- **143 条自动化测试**：接口层 111 条 + 端到端 32 条，纯标准库实现，可重复执行

---

## 🛠 技术栈

### 后端
| 类别 | 技术 | 版本 |
|---|---|---|
| Web 框架 | FastAPI + Uvicorn | 0.115 |
| LLM 编排 | LangChain / LangGraph | 0.3 / 0.2 |
| ORM | Tortoise ORM（asyncpg / aiomysql） | 0.21 |
| 业务库 | MySQL | 8 |
| 向量库 | PostgreSQL + pgvector | pg16 |
| 中文分词 | jieba | 0.42 |
| 鉴权 | PyJWT + passlib | 2.10 / 1.7 |
| 文档解析 | pypdf / python-docx / openpyxl | — |

### 前端
| 类别 | 技术 | 版本 |
|---|---|---|
| 框架 | Vue 3（Composition API） | 3.5 |
| 构建 | Vite | 6.0 |
| UI | Element Plus | 2.9 |
| 图表 | ECharts | 5.6 |
| 路由 | Vue Router | 4.5 |
| HTTP | Axios | 1.7 |
| 部署 | Nginx（静态托管 + /api 反代） | alpine |

### 基础设施
- **Docker Compose** 编排 5 个容器（含按需启动的 Mock 沙箱）
- **大模型服务**：阿里云百炼（DashScope）—— `qwen-plus` / `text-embedding-v4` / `gte-rerank-v2`

---

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                            浏览器 / 用户                              │
│                   管理端（17 页面）  │  用户端问答（流式打字）           │
└───────────────────────┬──────────────────────────┬───────────────────┘
                        │ HTTP / SSE                │
                        ▼                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│              ai_frontend  (nginx:alpine,  :8080 → :80)               │
│         静态资源托管  +  /api 反向代理  +  SSE 关缓冲/长超时            │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ /api
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                ai_backend  (FastAPI + Uvicorn,  :9090)               │
│                                                                      │
│  ┌────────────┐  ┌────────────────────────────────────────────────┐  │
│  │  api/      │  │                  rag/                          │  │
│  │  16 个模块 │  │  ingest  解析→切分→向量化                        │  │
│  │  · auth    │  │  retriever  混合检索主管道（StageTrace 全程追踪） │  │
│  │  · kb      │  │  rewrite  多查询/指代消解/HyDE                   │  │
│  │  · doc     │  │  bm25    jieba 分词检索                         │  │
│  │  · chunk   │  │  fusion  RRF 名次融合                           │  │
│  │  · chat    │  │  rerank  gte-rerank-v2 重排                     │  │
│  │  · agent   │  │  qa      流式生成 + Function Calling            │  │
│  │  · eval    │  │  graph   LangGraph Agentic RAG 状态图           │  │
│  │  · model   │  │  judge   LLM-as-judge 四指标                    │  │
│  │  ...       │  │  tools   工具中心                               │  │
│  └────────────┘  └────────────────────────────────────────────────┘  │
└──────────┬───────────────────────┬──────────────────────┬────────────┘
           │                       │                      │
           ▼                       ▼                      ▼
   ┌───────────────┐      ┌──────────────────┐   ┌────────────────────┐
   │  ai_mysql     │      │  ai_pgvector     │   │  百炼 DashScope     │
   │  MySQL 8      │      │  PostgreSQL +    │   │  （真实大模型）      │
   │  :3307        │      │  pgvector :5432  │   │        或           │
   │  25 张业务表   │      │  kb_vectors 单表 │   │  ai_mock_llm 沙箱   │
   └───────────────┘      └──────────────────┘   └────────────────────┘
                                                          ▲
                            测试沙箱（--profile test）──────┘
                            假扮 chat / embedding / rerank
```

---

## 🔍 检索管线

本项目的核心是这条**可解释的混合检索管线**，每个阶段都会写入 `StageTrace` 供前端回放：

```
用户提问
   │
   ▼
① rewrite        查询改写（multi_query 多查询扩展 / coref 指代消解 / hyde 假设文档）
   │             量纲 none，不做召回
   ▼
② vector ∥ bm25  双通道并行召回
   │             向量：cosine 相似度（0~1）—— 阈值适用
   │             BM25：jieba 分词打分 —— 分数无上界，跨查询不可比，不适用阈值
   ▼
③ rrf            倒数排名融合（k=60）—— 名次分，不适用阈值
   │
   ▼
④ backfill       子块候选回填为父块（小块用来找，大块用来答）
   │
   ▼
⑤ rerank         重排模型精排（gte-rerank-v2，0~1）—— 阈值适用
   │
   ▼
最终上下文 → 生成答案
```

**为什么量纲要显式化？**

这是本项目一个重要的工程决策。常见错误是「拿 BM25 分数和 cosine 阈值直接比较」——这两者量纲完全不同：
- cosine 有明确上界 1，可以设阈值过滤
- BM25 分数无上界、随语料变化，设阈值毫无意义

因此每个阶段都标注 `scale`（量纲）与 `threshold_applies`（阈值是否适用），前端时间线可完整回放每一阶段的命中数与分数分布，避免误配参数。

---

## 📁 目录结构

```
.
├── docker-compose.yml          # 5 容器编排（mock-llm 走 profiles:["test"]）
├── LICENSE                     # MIT
├── README.md                   # 本文件
│
├── fastapi-app/                # 后端服务
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── settings.py             # 配置（环境变量可覆盖）
│   ├── models.py               # 25 张业务表 Tortoise ORM 模型
│   ├── main.py                 # 入口：初始化 + 种子数据 + 路由扫描
│   ├── api/                    # 16 个路由模块
│   │   ├── auth.py  users.py  dashboard.py  ai_model.py
│   │   ├── prompt.py  tool.py  knowledge_base.py
│   │   ├── document.py  chunk.py  split_strategy.py
│   │   ├── retrieval_strategy.py  retrieval.py
│   │   ├── chat_app.py  chat.py  agent.py  eval.py
│   ├── common/                 # 统一响应 / 异常 / 安全 / 依赖 / 分页
│   └── rag/                    # RAG 核心
│       ├── schemas.py          # StageTrace 量纲定义
│       ├── llm.py              # 模型工厂 + Prompt 模板（11 个内置）
│       ├── splitter.py         # 递归分块 / 父子分块
│       ├── parser.py           # PDF/Word/Excel/MD/TXT 解析
│       ├── vectorstore.py      # PGVector 访问（asyncpg 直连）
│       ├── bm25.py             # jieba 中文分词 BM25
│       ├── fusion.py           # RRF 融合
│       ├── rerank.py           # 重排（DashScope 原生接口）
│       ├── rewrite.py          # 多查询 / 指代消解 / HyDE
│       ├── retriever.py        # 混合检索主管道
│       ├── ingest.py           # 文档入库管道
│       ├── qa.py               # 流式生成 + 工具循环
│       ├── graph.py            # LangGraph Agentic RAG
│       ├── judge.py            # LLM-as-judge 四指标
│       └── tools.py            # 工具中心
│
├── vue/                        # 前端（Vue3 + Vite + Element Plus）
│   ├── Dockerfile              # 多阶段：node 构建 → nginx 托管
│   ├── nginx.conf              # 静态托管 + /api 反代 + SSE 关缓冲
│   ├── package.json
│   └── src/
│       ├── views/              # 15 个页面（登录/首页/知识库/文档/片段/...）
│       ├── components/         # AdminLayout 等
│       ├── api/                # request.js（Axios 封装）+ sse.js（POST 流式解析）
│       └── router/
│
├── mock-llm/                   # Mock 大模型沙箱（测试专用，纯标准库）
│   ├── Dockerfile
│   └── server.py               # OpenAI + DashScope 兼容服务
│
├── sql/
│   ├── ai_system.sql           # MySQL 25 表 DDL
│   └── pgvector_init.sql       # PGVector 建表 + 索引
│
├── tests/                      # 自动化测试（纯标准库，宿主机执行）
│   ├── harness.py              # HTTP/SSE 客户端 + 用例登记
│   ├── static_check.py         # AST 静态分析
│   ├── suite_api.py            # 接口层 111 条用例
│   ├── suite_e2e.py            # 端到端 32 条用例
│   └── setup_demo.py           # 一键准备演示数据
│
├── scripts/
│   ├── start.sh                # Linux / macOS / Git Bash 一键启动
│   └── start.bat               # Windows 一键启动
│
├── uploads/                    # 用户上传文档（运行时生成）
└── docs/                       # 项目文档
    ├── TEST_REPORT.md          # 测试报告（含缺陷详单）
    ├── PROJECT_PROGRESS.txt    # 项目进度跟踪
    ├── TODO_AND_PAID_ITEMS.txt # 待办与付费项说明
    └── DAILY_REPORT_*.txt      # 工作汇报
```

---

## 🚀 快速开始

### 前置要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| **Docker Desktop** | 最新版 | 必须；Windows 需启用 WSL2 后端 |
| **Git** | 任意 | 拉取代码 |
| **磁盘空间** | ≥ 5 GB | 镜像 + 数据卷 |

> **不需要**在宿主机安装 Python、Node.js 或任何项目依赖 —— 所有构建都在容器内完成。

### 第一步：克隆代码

```bash
git clone https://github.com/YouliGit/enterprise-knowledge-base.git
cd enterprise-knowledge-base
```

### 第二步：启动全部服务

**方式 A：一键脚本（推荐）**

```bash
# Windows（双击或在 cmd 中执行）
scripts\start.bat

# Linux / macOS / Git Bash
chmod +x scripts/start.sh && ./scripts/start.sh
```

**方式 B：手动执行**

```bash
docker compose up -d --build
```

首次构建需拉取基础镜像并安装依赖（约 5~15 分钟，取决于网络）。国内网络环境已默认配置加速源（Docker 走 `docker.m.daocloud.io`，pip 走阿里源，npm 走 npmmirror）。

### 第三步：验证服务

```bash
docker compose ps
```

应看到 4 个容器全部为 `Up`（`ai_mysql` / `ai_pgvector` 为 `Up (healthy)`）：

```
NAME           STATUS                   PORTS
ai_mysql       Up (healthy)             0.0.0.0:3307->3306/tcp
ai_pgvector    Up (healthy)             0.0.0.0:5432->5432/tcp
ai_backend     Up                       0.0.0.0:9090->9090/tcp
ai_frontend    Up                       0.0.0.0:8080->80/tcp
```

### 第四步：访问系统

| 入口 | 地址 | 说明 |
|---|---|---|
| **前端控制台** | http://localhost:8080 | 管理端 + 用户端问答 |
| **后端接口文档** | http://localhost:9090/docs | Swagger UI，可在线调试 |
| **健康检查** | http://localhost:9090/api/health | 返回 `{"code":0,"data":{"status":"up"}}` |

**默认账号：`admin` / `admin`**

### 停止 / 清理

```bash
# 停止服务（保留数据）
docker compose down

# 停止并删除数据卷（清空数据库，慎用）
docker compose down -v
```

---

## 🧪 零成本体验（Mock 大模型沙箱）

真实推理走阿里云百炼（**付费**）。如果你想**不花钱**先把整套链路跑通、或做功能验收，可以启用内置的 Mock 大模型沙箱。

### 什么是 Mock 沙箱

`mock-llm/` 是一个**纯 Python 标准库**实现的假大模型服务，在沙箱内假扮三家云端模型：

| 接口 | 假扮对象 | 说明 |
|---|---|---|
| `POST /v1/chat/completions` | 对话模型 | OpenAI 兼容，支持 **stream 流式** + **tool_calls 函数调用** |
| `POST /v1/embeddings` | 向量模型 | 确定性 hashing-trick 向量化（同文本恒得同向量） |
| `POST /api/v1/services/rerank/...` | 重排模型 | DashScope 原生接口格式 |
| `POST /_control` | — | 故障注入（如「让接下来 2 次调用返回 500」），用于验证降级路径 |

**特点**：不联网、不花钱、结果确定可复现、支持故意注入故障。

### 启用沙箱并准备演示数据

```bash
# 1. 带 test profile 启动（会多起一个 ai_mock_llm 容器）
docker compose --profile test up -d --build

# 2. 确认沙箱存活
curl http://127.0.0.1:8898/health
# → {"status": "up", "dim": 1024, "topk": 32}

# 3. 一键准备演示数据（模型配置 + 知识库 + 3 份文档 + 策略 + 2 个问答应用）
cd tests
python setup_demo.py
```

> 第 3 步需要宿主机有 Python 3（仅用标准库，无需安装任何依赖）。
> 它会自动清理历史脏数据，并打印出所有演示资源的 ID。

脚本执行完成后，你会得到：

- **3 个模型配置**（全部指向沙箱，已通过连通性测试）
- **1 个知识库**：`演示知识库(企业制度与产品)`，含 3 份已入库文档
- **1 套检索策略**：`演示-混合检索(宽松阈值)`
- **2 个问答应用**：`演示应用-普通问答`、`演示应用-Agentic RAG`

### 体验路线

1. 登录 http://localhost:8080（`admin` / `admin`）
2. **首页 Dashboard** —— 查看 12 项统计指标与架构概览
3. **检索测试** —— 选「演示知识库」+「演示-混合检索(宽松阈值)」，输入
   `光模块的工作温度范围是多少`，观察 **StageTrace 六阶段时间线**（重点看各阶段量纲与阈值适用性标注）
4. **召回调试台** —— 多套策略并排对比
5. **Agent 运行记录** —— 查看节点时间线回放
6. **用户端问答** —— 选「演示应用-普通问答」，体验逐字流式打字 + 引用来源表格
7. 切换到 **Agentic RAG 应用**，试试问 `123*(45+67) 等于多少` 触发计算器工具调用

### 使用真实大模型（百炼）

1. 前往 [阿里云百炼控制台](https://bailian.console.aliyun.com/) 开通服务并创建 API-KEY（**付费项**）
2. 登录系统 → **AI 配置 → AI模型配置** → 编辑三类模型，填入 Key，`api_base` 改为百炼官方地址：
   - 对话：`https://dashscope.aliyuncs.com/compatible-mode/v1`（模型 `qwen-plus`）
   - 向量：`https://dashscope.aliyuncs.com/compatible-mode/v1`（模型 `text-embedding-v4`，维度 1024）
   - 重排：`https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank`（模型 `gte-rerank-v2`）
3. 每类模型点「测试」验证连通性

> ⚠️ 注意：重排接口是 DashScope **原生**格式，`api_base` **不带** `/v1` 后缀；对话与向量走 OpenAI 兼容模式，**带** `/v1`。这是常见的配置踩坑点。

---

## 📘 使用指南

### 完整配置流程（从零开始）

若不用演示数据脚本，按以下顺序手动配置：

```
① AI配置 → AI模型配置      添加 chat / embedding / rerank 三类模型并测试连通
② AI配置 → Prompt模板      导入内置模板（11 个，含问答/改写/裁判等）
③ AI配置 → 工具中心        导入内置工具（计算器 / 当前时间 / 知识库检索）
④ 知识库管理 → 切分策略    配置父子分块参数（块大小 / 重叠）
⑤ 知识库管理 → 检索策略    配置召回参数（top_k / 阈值 / 是否改写 / 是否重排）
⑥ 知识库管理 → 知识库      新建知识库并绑定向量模型
⑦ 上传文档                 拖拽上传 → 等待解析完成（轮询状态）
⑧ 片段管理                 人工检查/修正片段（修改后自动重新向量化）
⑨ 检索测试                 验证召回效果（看 StageTrace）
⑩ 问答应用管理             新建应用，绑定知识库 + 模型 + 策略（可选 Agent 模式）
⑪ 用户端问答               选择应用开始对话
```

### 评测流程

```
① 评测中心 → 数据集       新建数据集，导入用例
② 导入用例                每条含：问题 / 标准答案 / 来源片段ID（用于计算 Context Recall）
③ 批量评测                选数据集 + 知识库 + 策略 → 运行 → 产出四指标
④ 策略对比                多套策略跑同一数据集，横向对比综合分
```

---

## ✅ 测试

项目自带 **143 条自动化测试**（接口层 111 + 端到端 32），纯标准库实现，可在宿主机直接运行（无需安装第三方依赖）。

### 运行前提

- 服务已启动（推荐带 `--profile test` 以便跑端到端用例）
- 宿主机有 Python 3

### 执行

```bash
cd tests

# 1. AST 静态检查：扫描「引用未导入的全局名」
#    （本项目 try/except 会静默吞掉 NameError，这是重要防线）
python static_check.py

# 2. 接口层测试：111 条用例（登录/权限/CRUD/契约/安全/边界）
python suite_api.py

# 3. 端到端测试：32 条用例（真实业务全链路）
python suite_e2e.py
```

### 预期输出

```
静态检查完成：扫描 42 个文件，0 个文件存在可疑引用

===== 接口层测试汇总：111/111 通过，0 失败 =====
===== 端到端测试汇总：32/32 通过，0 失败 =====
```

结果同时落盘至 `tests/results/api_results.json` 与 `tests/results/e2e_results.json`，含每条用例的期望 / 实际 / 证据，可直接用于生成报告。

### 测试覆盖概览

| 套件 | 用例数 | 覆盖内容 |
|---|---|---|
| `suite_api.py` | 111 | 登录鉴权、权限越权、用户管理、知识库、文档、片段、策略配置、对话、评测、Agent、仪表盘、契约一致性、安全（SQL 注入 / XSS / 路径穿越 / 类型攻击） |
| `suite_e2e.py` | 32 | 模型连通 → Prompt/工具 → 文档入库 → 片段管理 → 混合检索（StageTrace / 量纲 / BM25 兜底） → 召回对比 → SSE 问答 → Agentic RAG → 评测 → 策略对比 → 并发稳定性 |
| `static_check.py` | 42 文件 | AST 检查未导入的全局名引用 |

详细测试结论与缺陷记录见 [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md)。

### 故障注入测试

Mock 沙箱支持故意制造故障，用于验证系统的降级与容错行为：

```bash
# 让接下来 2 次对话调用返回 500
curl -X POST http://127.0.0.1:8898/_control \
     -H "Content-Type: application/json" \
     -d '{"fail": {"chat": 2}}'

# 查看调用统计
curl http://127.0.0.1:8898/_control

# 重置
curl -X POST http://127.0.0.1:8898/_control -d '{"reset": true}'
```

---

## ⚙️ 配置说明

### 环境变量（docker-compose.yml）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `root123456` | MySQL 密码（**生产必须修改**） |
| `MYSQL_DATABASE` | `ai_system` | 业务库名 |
| `POSTGRES_PASSWORD` | `root123456` | PostgreSQL 密码（**生产必须修改**） |
| `POSTGRES_DB` | `vector_store` | 向量库名 |
| `JWT_SECRET` | `ai-system-secret-please-change` | JWT 签名密钥（**生产必须修改**） |
| `EMBEDDING_DIM` | `1024` | 向量维度，须与向量模型一致 |
| `DASHSCOPE_API_KEY` | 空 | 百炼 Key，留空时相关接口报错属预期行为 |
| `APP_PORT` | `9090` | 后端端口 |

### 端口映射

| 服务 | 宿主端口 | 容器端口 | 说明 |
|---|---|---|---|
| 前端 | 8080 | 80 | nginx |
| 后端 | 9090 | 9090 | FastAPI |
| MySQL | **3307** | 3306 | 宿主 3306 常被占用，故改用 3307 |
| PostgreSQL | 5432 | 5432 | 向量库 |
| Mock 沙箱 | 8898 | 8000 | 仅绑定 `127.0.0.1` |

### 数据库连接

```bash
# 进入 MySQL
docker exec -it ai_mysql mysql -uroot -proot123456 ai_system

# 进入 PostgreSQL
docker exec -it ai_pgvector psql -U postgres -d vector_store
```

### 修改代码后如何生效

后端代码**通过镜像构建**打入容器（仅 `uploads/` 目录是挂载的），因此修改后端代码后需要：

```bash
# 方式 A：重新构建（推荐，适合正式改动）
docker compose up -d --build backend

# 方式 B：快速热替换单个文件（适合调试）
docker cp fastapi-app/rag/qa.py ai_backend:/app/rag/qa.py
docker restart ai_backend
```

前端同理：修改 `vue/src/` 后需 `docker compose up -d --build frontend`。

### 前端本地开发（可选）

如需在宿主机调试前端（后端仍在 Docker）：

```bash
cd vue
cp .env.example .env.local    # 按需修改
npm install                    # 已配置 npmmirror 镜像
npm run dev                    # 默认 http://localhost:5173
```

---

## 🔧 常见问题排查

### 1. 构建时镜像拉取超时

项目已默认使用国内加速源。若仍失败，可以：

```bash
# 手动拉取基础镜像
docker pull docker.m.daocloud.io/library/mysql:8
docker pull docker.m.daocloud.io/pgvector/pgvector:pg16
docker pull docker.m.daocloud.io/library/python:3.11-slim
docker pull docker.m.daocloud.io/library/node:20-alpine
docker pull docker.m.daocloud.io/library/nginx:alpine
```

或配置 Docker Desktop → Settings → Docker Engine 中的 `registry-mirrors`。

### 2. 端口被占用

| 问题 | 解决 |
|---|---|
| 8080 被占用 | 修改 `docker-compose.yml` 中 frontend 的 `ports: "8080:80"` → 如 `"8081:80"` |
| 9090 被占用 | 修改 backend 的 `ports: "9090:9090"` |
| 3307 / 5432 被占用 | 修改对应服务的宿主端口映射 |

### 3. 文档上传后一直显示「解析中」

排查步骤：

```bash
# 看后端日志
docker compose logs -f backend | grep -i "ingest\|error"
```

常见原因：
- 扫描件 PDF（无文字层）需要 OCR，当前未接 OCR 引擎会失败
- 大模型 Key 未配置 → 向量化步骤失败

若需重置某个文档状态，可在「文档管理」页面点「重新解析」。

### 4. 问答报 401 / 「无 key」错误

这是 **预期行为** —— 未配置百炼 API Key 时，模型调用会失败。解决：

- 配置真实 Key（**付费**），或
- 使用 Mock 沙箱（见[零成本体验](#-零成本体验mock-大模型沙箱)）

### 5. 检索结果为空

按顺序检查：

1. 文档是否已 `parsed` 且 `chunk_count > 0`
2. 知识库「重建索引」页面的 `vector_count` 是否与片段数一致
3. 检索策略的 **cosine 阈值是否过高**（沙箱向量分布偏低，建议 0.10 左右；真实模型可用 0.30）
4. 检索测试页面查看 **StageTrace**，定位是哪个阶段把结果过滤掉了

### 6. SSE 问答卡住不返回

可能原因：反向代理缓冲了流式响应。项目 `vue/nginx.conf` 已配置 `X-Accel-Buffering: no` 与长超时；若自行改过 nginx 配置，请确认保留了这些设置。

### 7. 数据库初始化失败 / 表不存在

```bash
# 彻底重建（会清空数据）
docker compose down -v
docker compose up -d --build
```

初始化 SQL 仅在**数据卷为空**时执行，因此必须配合 `-v` 删除旧卷。

### 8. Windows 下 WSL2 相关问题

- 确保 Docker Desktop → Settings → General 勾选了 `Use WSL 2 based engine`
- 若 WSL2 未安装：`wsl --install` 后重启

---

## 🔌 接口概览

所有接口统一前缀 `/api`，统一返回结构 `{code, msg, data}`（`code=0` 表示成功，非 0 为业务错误，此时 HTTP 状态码仍为 200）。

| 模块 | 主要接口 | 说明 |
|---|---|---|
| **认证** | `POST /login`、`POST /register`、`GET /me` | JWT 鉴权 |
| **用户管理** | `GET/POST/PUT/DELETE /admin/user*` | 管理员功能，含禁用/重置密码 |
| **模型配置** | `GET/POST/PUT/DELETE /aiModel*`、`POST /aiModel/{id}/test` | 三类模型 + 连通性测试 |
| **Prompt** | `GET/POST/PUT/DELETE /prompt*`、`POST /prompt/importBuiltin` | 模板管理 |
| **工具中心** | `GET/POST/PUT/DELETE /tool*`、`POST /tool/importBuiltin` | Function Calling 工具 |
| **知识库** | `GET/POST/PUT/DELETE /knowledgeBase*` | 含 `rebuild_status`、`rebuild` |
| **文档** | `POST /document/upload`、`GET /document/page`、`PUT /document/{id}/reparse` | 上传与状态轮询 |
| **片段** | `GET /chunk/page`、`PUT /chunk/{id}`、`PUT /chunk/{id}/status` | 人工修正（自动重新向量化） |
| **策略** | `GET/POST/PUT/DELETE /splitStrategy*`、`/retrievalStrategy*` | 切分与检索策略 |
| **检索** | `POST /retrieval/test`、`POST /retrieval/compare` | 含完整 StageTrace、多策略对比 |
| **问答应用** | `GET/POST/PUT/DELETE /chatApp*`、`PUT /chatApp/{id}/kbs` | 绑定知识库 |
| **对话** | `POST /chat/session`、`POST /chat/ask`（SSE）、`GET /chat/history/{sid}` | 流式问答 |
| **Agent** | `POST /agent/run`、`GET /agent/run/page`、`GET /agent/run/{id}/steps` | 运行记录与时间线 |
| **评测** | `GET/POST/DELETE /eval/dataset*`、`POST /eval/run`、`POST /eval/compare` | 四指标 + 策略对比 |
| **仪表盘** | `GET /dashboard/summary` | 12 项统计指标 |
| **日志** | `GET /operationLog/page`、`GET /toolCallLog/page` | 操作与工具调用日志 |
| **健康检查** | `GET /health` | 存活探测 |

完整接口文档（可在线调试）：http://localhost:9090/docs

### SSE 事件协议

`POST /api/chat/ask` 返回 `text/event-stream`，事件类型：

| 事件 | 载荷 | 说明 |
|---|---|---|
| `start` | `{session_id, app, use_agent}` | 开始 |
| `agent_start` | `{run_id}` | Agent 模式开始 |
| `step` | `{data}` | Agent 节点执行（节点名/思考/输入输出） |
| `trace` | `{data}` | 检索阶段追踪（StageTrace） |
| `token` | `{delta}` | 逐 token 增量 |
| `refs` | `{refs}` | 引用来源列表 |
| `done` | `{message_id, cost_ms, agent_run_id}` | 完成 |
| `error` | `{message}` | 错误 |

> ⚠️ 注意：该接口是 **POST**，浏览器原生 `EventSource` 不支持，前端使用自实现的 `sseFetch`（基于 `fetch` + `ReadableStream`）解析。

---

## 📐 设计约定

改动代码时请遵循以下既定口径（否则可能与其他模块不一致）：

| 约定 | 内容 |
|---|---|
| **返回结构** | 统一 `{code, msg, data}`；业务异常 `BizException` → HTTP 200 + `code != 0` |
| **SSE 事件** | `start` / `agent_start` / `step` / `token` / `refs` / `trace` / `done` / `error` |
| **检索量纲** | cosine(0~1，阈值适用) / bm25(无上界，不适用) / rrf(名次，不适用) / rerank(0~1，阈值适用) |
| **向量表** | 仅 `kb_vectors` 一张；`chunk_id` 唯一键；**父块不入向量库** |
| **分块模式** | `parent_child`（父块供答、子块供找）/ `recursive`（无父块） |
| **评测 Context Recall** | 不靠模型，用用例 `source_chunk_ids` 做集合运算 |
| **裁判温度** | LLM-as-judge 一律 `temperature=0` |
| **BM25 索引** | 进程内缓存 `{kb_id: index}`，片段修正/重建时失效 |
| **模型配置缓存** | 读库带 2 秒 TTL，改配置 ≤2 秒生效 |
| **鉴权** | 前端统一 `Authorization: Bearer <token>` |

### 已知技术陷阱（改造代码时务必注意）

1. **Tortoise ORM + MySQL：`bulk_create` 不回填自增主键**（仅 PostgreSQL 支持 `RETURNING`）。
   批量插入后需用主键建关联的场景，必须回查（见 `rag/ingest.py::_fetch_ids`）。
2. **asyncio 后台任务必须保存强引用**，否则事件循环只持弱引用，任务会被 GC 中途回收
   （表现为文档永久卡在 `parsing`）。
3. **保存内容后重新向量化，必须「先落库再 reembed」**，否则重读旧值会覆盖编辑。
4. **HTTP/1.1 的 SSE 响应必须有 `Transfer-Encoding: chunked`**，否则客户端永久挂起。
5. **LangGraph 节点拿到的是 state 副本**，节点内改动不回流，需从库中取真实值
   （如 `agent_step.seq` 以 `max(seq)` 为准）。
6. **测试 SSE 必须用增量解码**（`codecs.getincrementaldecoder`），
   逐字节 `decode` 会撕裂多字节中文。
7. **测试轮询文档状态必须等「全部进入终态」**，`parsing` 不算收敛。

---

## ⚠️ 已知限制

| 限制 | 说明 |
|---|---|
| **OCR 未内置** | 扫描件 PDF（无文字层）无法解析，需自行接入 OCR 引擎 |
| **大模型依赖外部 API** | 真实推理需阿里云百炼（付费）；Mock 沙箱仅用于功能验证，答案质量不代表真实效果 |
| **向量维度固定 1024** | 更换向量模型需同步修改 `EMBEDDING_DIM` 与 `pgvector_init.sql`，并重建向量表 |
| **单机部署** | 未做水平扩展与分布式设计，适合中小规模知识库 |
| **前端未做自动化测试** | 当前测试聚焦后端接口与全链路，前端 UI 为人工验证 |
| **默认凭据为弱口令** | 见[安全警告](#️-安全警告部署前必读)，生产环境必须修改 |

---

## 📄 相关文档

| 文档 | 内容 |
|---|---|
| [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) | 测试报告：环境、用例设计、执行结果、缺陷详单（含诊断证据） |
| [`docs/PROJECT_PROGRESS.txt`](docs/PROJECT_PROGRESS.txt) | 项目进度跟踪与技术决策记录 |
| [`docs/TODO_AND_PAID_ITEMS.txt`](docs/TODO_AND_PAID_ITEMS.txt) | 待办事项与付费依赖说明 |

---

## 📜 License

本项目基于 [MIT License](LICENSE) 开源。
