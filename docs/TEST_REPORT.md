# AI Agentic RAG 企业知识库平台 — 软件测试报告

| 项目 | 内容 |
|---|---|
| 报告日期 | 2026-09-21 |
| 测试对象 | 企业知识库 AI 系统（`D:\linshidaimaaaaaaaaa\企业知识库\ai_system`） |
| 被测架构 | FastAPI + LangChain + LangGraph + Tortoise ORM + MySQL 8 + PostgreSQL/PGVector + Vue 3，5 容器 Docker 编排 |
| 测试标准 | GB/T 25000.51 软件质量要求与评价 + 通用软件测试规范 |
| 测试方法 | 黑盒功能测试、等价类划分、边界值分析、错误推测、安全测试、接口契约测试、权限越权测试、并发稳定性测试、AST 静态分析、回归测试 |
| 执行方式 | 真实运行（非静态审阅）：Docker 沙箱内起 5 容器，用 Mock 大模型替代付费 API，Python 标准库自动化执行 |
| 环境约束 | 全程仅在项目文件夹内工作；依赖走国内源；百炼等付费 API Key 一律留空（由 Mock 沙箱承担） |
| 测试工具 | `tests/harness.py`（HTTP/SSE 客户端 + 用例登记）、`tests/static_check.py`（AST 检查）、`tests/suite_api.py`（接口层）、`tests/suite_e2e.py`（端到端） |

---

## 一、测试环境

### 1.1 容器编排（`docker compose --profile test up -d`）

| 容器 | 镜像/角色 | 端口 | 状态 |
|---|---|---|---|
| `ai_mysql` | MySQL 8（utf8mb4，25 张业务表） | 3307→3306 | healthy |
| `ai_pgvector` | PostgreSQL + pgvector（`kb_vectors` 向量表） | 5432→5432 | healthy |
| `ai_backend` | FastAPI 后端（84 个 REST 接口） | 9090→9090 | up |
| `ai_frontend` | nginx + Vue 3 静态资源 | 8080→80 | up |
| `ai_mock_llm` | **Mock 大模型沙箱**（纯标准库实现的 OpenAI/DashScope 兼容服务） | 8898→8000 | healthy |

### 1.2 Mock 大模型沙箱能力

不调用真实付费大模型即可完成全链路验证，覆盖：

- `POST /v1/chat/completions` —— 兼容 OpenAI 协议，支持 **stream 流式**、**tool_calls 函数调用**，并按 Prompt 特征词自动识别任务类型（rewrite / hyde / evaluate / self_check / judge / answer）
- `POST /v1/embeddings` —— 确定性 hashing-trick 向量化（同文本恒得同向量，中文二元组加权模拟语义近似）
- `POST /api/v1/services/rerank/text-rerank/text-rerank` —— DashScope 兼容重排
- `/_control` —— 故障注入（`chat=2` 让接下来 2 次对话返回 500）与调用计数，用于验证**降级路径**

> 该沙箱使「测试可离线、可重复、零成本」，同时保留了真实协议的边界条件（分块传输、tool_calls 分片、超时等）。

---

## 二、测试范围与用例设计

### 2.1 接口层套件（`suite_api.py`，111 条用例）

| 模块 | 覆盖内容 |
|---|---|
| A 登录与会话 | 正常登录、密码错、账号不存在、空值、非法 JSON、JWT 无 Token / 伪造 / 截断 / 有效 |
| B 用户管理 | 管理员 CRUD、重置密码、分页边界（page=0、超大 page_size）、模糊查询、删除 |
| C 权限越权 | 普通用户访问管理端 5 个接口须 403；共享数据可访问 |
| D 用户管理专项 | 创建/修改/禁用/启用/重置密码/删除/不能删自己/不存在用户 |
| E 知识库与文档 | CRUD、检索测试、召回对比、文档与片段分页 |
| F 策略与配置 | 切分策略、检索策略、AI 模型、Prompt、工具中心、问答应用 |
| G 对话与会话 | 历史记录边界（ID=0/-1/不存在）、反馈、删除 |
| H 评测与 Agent | 数据集/用例/运行/对比分页、Agent 步骤查询、友好报错 |
| I 仪表盘与日志 | 12 项首页指标、架构说明、操作日志、工具调用日志、健康检查 |
| J 契约一致性 | 21 个核心接口统一 `{code, msg, data}` 结构 |
| K 安全测试 | SQL 注入、XSS、路径穿越、参数类型攻击、超大分页截断 |
| R 历史缺陷回归 | 上一轮修复过的缺陷专项复核 |

### 2.2 端到端套件（`suite_e2e.py`，32 条用例）

按真实业务链路串联，**跨模块验证**：

```
1 模型配置与连通性 → 2 Prompt 与工具中心 → 3 知识库与文档入库（解析→切分→向量化）
→ 4 片段管理（人工修正/停用启用/向量同步）→ 5 混合检索（StageTrace 量纲/命中正确性/BM25 兜底/双策略对比）
→ 6 问答应用与 SSE 流式问答 → 7 Agentic RAG（状态图/时间线/自查/工具闭环）
→ 8 LLM-as-judge 评测与策略对比 → 9 并发与稳定性
```

---

## 三、测试执行结果

### 3.1 总体结果

| 套件 | 修复前 | 修复后 | 提升 |
|---|---|---|---|
| 接口层（111 条） | 106/111 | **111/111** | +5 |
| 端到端（32 条） | 8/32 | **32/32** | +24 |
| AST 静态检查（42 文件） | 1 处可疑引用 | **0 处** | 修复 |
| Mock 调用异常 | — | 0 errors | 全绿 |

> 端到端通过率演进：`8/32 → 17/32 → 26/32 → 28/32 → 29/32 → 31/32 → 32/32`

### 3.2 分类统计（修复后）

| 测试类型 | 用例数 | 通过 | 失败 |
|---|---|---|---|
| 功能测试 | 71 | 71 | 0 |
| 边界值测试 | 14 | 14 | 0 |
| 权限/越权测试 | 6 | 6 | 0 |
| 安全测试 | 6 | 6 | 0 |
| 契约一致性测试 | 1（覆盖 21 接口） | 1 | 0 |
| 稳定性/并发测试 | 2 | 2 | 0 |
| **合计** | **143** | **143** | **0** |

---

## 四、缺陷清单（本轮共 13 项，含 3 项 P0）

> 分级：P0 = 阻断核心链路；P1 = 功能不可用或数据错误；P2 = 体验/健壮性。

### 缺陷 #1（P1）Agent 自查节点从未真正执行 —— `NameError` 被静默吞掉

- **现象**：Agentic RAG 的 `self_check` 节点看似正常返回，实际从未调用裁判模型，自查形同虚设。
- **根因**：`rag/graph.py` 的 `node_self_check` 局部 `import` 漏了 `get_chat_model`，触发 `NameError` 后被上层 `except` 静默捕获，节点降级为空操作。
- **证据**：AST 静态检查报出「引用未导入的全局名」1 处；修复后归零。
- **修复**：补全 `from rag.llm import get_chat_model, get_prompt, render_prompt`。
- **验证**：E2E-7.3「Agent 自查节点真实执行」thought=`答案均可由参考资料支撑`，确认真实调用裁判。

### 缺陷 #2（P1）工具 / Prompt 列表模糊查询报服务器内部错误

- **现象**：`/api/tool/page?query=x`、`/api/prompt/page?query=x` 返回服务器内部错误。
- **根因**：`api/tool.py`、`api/prompt.py` 用 `QuerySet | QuerySet` 做并集，Tortoise ORM 不支持该运算符，抛 `TypeError`。
- **修复**：改用 `from tortoise.expressions import Q` + `qs.filter(Q(a__icontains=q) | Q(b__icontains=q))`。
- **验证**：接口套件 R1/R2 由 FAIL → PASS。

### 缺陷 #3（P0）整条检索链路崩溃 —— `_backfill_stage` 缺参数

- **现象**：任何一次检索（含检索测试、问答、Agent）直接 500，功能完全不可用。
- **根因**：`rag/retriever.py` 的 `_backfill_stage` 内部使用 `strategy.candidate_limit`，但函数签名未接收 `strategy`，抛 `NameError: name 'strategy' is not defined`。
- **修复**：签名补 `strategy: RetrievalStrategy` 参数，`retrieve_once` 调用点补传。
- **验证**：E2E-5.1~5.4 全部通过，StageTrace 六阶段（rewrite/vector/bm25/rrf/backfill/rerank）齐备。

### 缺陷 #4（P0，最严重）文档入库 100% 失败 —— 向量表 `chunk_id` 非空约束被违反

- **现象**：任意文档上传后状态变 `failed`，报 `NotNullViolationError: null value in column "chunk_id" of relation "kb_vectors"`。**知识库产品最核心的入库功能完全不可用。**
- **根因**：Tortoise ORM 0.21.7 + MySQL 组合下，`bulk_create` **不回填自增主键**（仅 PostgreSQL 支持 `RETURNING`）。代码依赖 `chunk.id` 建立「子块 → 父块」引用与「向量 → 子块」关联，结果 `c.id` 全为 `None`，导致向量 `chunk_id=NULL`、子块 `parent_id=NULL`。
- **诊断证据**：
  ```
  bulk_create 后 ids = [None, None, None]     ← c.id 未被回填
  DB 实际插入     = 58, 59, 60                ← 主键确实生成了，只是没回传到对象
  单条 create()   = 61                        ← 对照组：单条写入正常
  ```
- **修复**：新增 `_fetch_ids(doc_id, is_parent, expect)`，在 `bulk_create` 后按 `doc_id + is_parent + seq` 回查真实主键，并校验条数：
  ```python
  async def _fetch_ids(doc_id: int, is_parent: int, expect: int) -> list[int]:
      rows = await Chunk.filter(doc_id=doc_id, is_parent=is_parent).order_by("seq").values("id", "seq")
      ids = [r["id"] for r in rows[-expect:]] if expect else []
      if len(ids) != expect:
          raise RuntimeError(f"片段主键回查异常：期望 {expect} 条，实际 {len(ids)} 条（doc_id={doc_id}）")
      return ids
  ```
  父块、子块分别回查；先算 `child_parent_ids` 再入库；向量行以 `child_id_list[idx]` 作 `chunk_id`。
- **验证**：E2E-3.1~3.4 全通（`vector=4 chunk=4`），端到端通过率 8/32 → 17/32。

### 缺陷 #5（P1）脏工具配置拖垮整个问答 / Agent 链路

- **现象**：库里残留一条 `schema_json='{}'` 的测试工具，被原样送进 `bind_tools`，报 `Unsupported function {}`，导致**所有**问答与 Agent 请求失败。
- **根因**：`get_enabled_tools()` 未校验 `schema_json` 合法性，直接透传。
- **修复**：新增 `_normalize_schema(raw)`，容忍「外层包装」与「内层平铺」两种写法；缺 `name` 视为非法并跳过（只 warning 不抛出）；`name` 与 `code` 不一致时以 `code` 为准，保证 `execute_tool` 能回查。写入端（`api/tool.py`）同步加校验。
- **验证**：通过率 17/32 → 26/32；接口套件工具相关用例全通。

### 缺陷 #6（P1）Agent 状态图无限循环 —— `GraphRecursionError`

- **现象**：Agent 调试接口报 `GraphRecursionError: Recursion limit of 25`。
- **根因**：`route_after_evaluate` 用 `rounds_used < 4` 判收敛，但 `rounds_used` 是 `app_retrieve` 内部轮次（恒为 1），图级 `state["round"]` 从未被使用 → 「改写→检索→评估」分支永不收敛。
- **修复**：改用图级 `state["round"]`，引入常量 `AGENT_MAX_ROUNDS = 3`、`AGENT_RECURSION_LIMIT = 50`；`node_retrieve` 回写 `rounds_used`；`run_agent` 以 `config={"recursion_limit": ...}` 调用。
- **验证**：诊断从「25 层递归报错」→ E2E-7.1 / 7.2 正常收敛（`rounds=1`，节点齐备）。

### 缺陷 #7（P1）Agent 时间线 `seq` 全部为 1

- **现象**：`agent_step` 表内 4 个节点的 `seq` 全是 `[1,1,1,1]`，前端时间线无法正确排序。
- **根因**：`_emit_step` 试图用 `state["seq"]` 计数，但 LangGraph 节点拿到的是 **state 副本**，节点内改动不会回流到共享 state，计数永远停留在初值。
- **修复**：新增 `_next_seq()`，以**数据库中该 run 的 max(seq)** 为准递增，绕开 state 副本问题。
- **验证**：E2E-7.2 `seq=[1, 2, 3, 4]` 唯一递增。

### 缺陷 #8（P1）Agent 自查失败后仍无限重试

- **现象**：自查连续不通过时，图在 `generate ↔ self_check` 之间的重试分支打转。
- **根因**：重试轮到达上限后 `check_retries` 不再自增，但 `check.sufficient` 仍为 `False`，`route_after_self_check` 按旧逻辑永远返回 `generate`。
- **修复**：`node_generate` 返回显式标记 `self_check_retry: False`，`node_self_check` 在重试轮置 `True`，路由改为 `return "generate" if state.get("self_check_retry") else END`。
- **验证**：E2E-7 全组通过。

### 缺陷 #9（P1）SSE 异常路径下 Agent 运行记录卡在 `running`

- **现象**：问答过程中抛出异常时，`agent_run.status` 永远停留在 `running`，且 SSE `error` 事件消息为空，前端只看到空白失败。
- **根因**：`api/chat.py` 的 SSE producer 未在异常分支落库，也未规范化错误消息。
- **修复**：新增 `logger.exception`；`agent_run` 变量提升到 `try` 之前；`BizException` / `Exception` 两分支均置 `failed` 并写 `final_answer`；错误消息统一为 `f"{type(e).__name__}: {e}".strip().rstrip(":") or repr(e)`。
- **验证**：E2E-7.5 运行记录状态全部 `done`；异常场景可正确落 `failed`。

### 缺陷 #10（P0）Mock 沙箱 SSE 响应永久挂起

- **现象**：`StreamingResponse` 的 `astream` 调用永久阻塞，诊断脚本被 SIGTERM 强杀。
- **根因**：Mock 服务声明 `protocol_version = "HTTP/1.1"`，但 SSE 响应**既无 `Content-Length` 也无 `Transfer-Encoding`**。HTTP/1.1 下客户端（httpx / openai SDK）无法判定响应体结束，只能一直等。
- **修复**：SSE 路径改用**分块传输编码**（chunked）：`_sse_start()` 补 `Transfer-Encoding: chunked`，新增 `_write_chunked()` / `_chunked_end()`，结束帧按 HTTP/1.1 分块格式写出。
- **验证**：`astream` 由「永久挂起」→ 正常产出 15 个非空 chunk，拼接出完整答案。

### 缺陷 #11（P1）并发上传后台任务被 GC 中途回收

- **现象**：并发上传 8 个文档时部分文档永久卡在 `parsing`，后台任务「凭空消失」。
- **根因**：`spawn_ingest` 用 `asyncio.get_event_loop().create_task()` 创建任务却**不保存引用**。Python 事件循环对 task 仅持**弱引用**，无强引用时任务会被 GC 中途回收，入库逻辑执行到一半即中断。
- **修复**：引入模块级强引用集合 + 安全包装：
  ```python
  _BG_TASKS: set[asyncio.Task] = set()

  def spawn_ingest(doc_id: int):
      try:
          loop = asyncio.get_running_loop()
      except RuntimeError:
          loop = asyncio.get_event_loop()
      task = loop.create_task(_run_ingest_safe(doc_id))
      _BG_TASKS.add(task)
      task.add_done_callback(_BG_TASKS.discard)
      return task
  ```
  `_run_ingest_safe` 兜底把异常写入 `doc.status = "failed"` + `error`，避免永久 `parsing`。
- **验证**：E2E-9.1 8/8 全部 `parsed`（独立验证耗时约 1.0s）。

### 缺陷 #12（P1，数据丢失）片段人工修正被静默还原

- **现象**：管理员在「片段管理」里修正片段内容并保存，接口返回成功、长度也变了，但**刷新后内容回到修改前的旧值**，用户编辑静默丢失。
- **根因**：`api/chunk.py` 的更新逻辑只改了内存对象 `c.content`，**未先落库**就调用 `reembed_chunk(cid)`；而 `reembed_chunk` 会**重新从数据库读取内容**，读到的是旧值，随即 `save()` 把用户的编辑覆盖掉。
- **证据**：修复前反复操作 `len=447` 始终不变；修复后 `len=468`。
- **修复**：
  ```python
  c.content = body.content
  c.char_len = len(body.content)
  await c.save()          # 必须先落库，否则 reembed_chunk 会读回旧内容覆盖编辑
  await reembed_chunk(cid)
  ```
  同时加固 `reembed_chunk`：父块只同步 `char_len`；子块以库中最新内容为准（并明确要求调用方先 `save()`）。
- **验证**：E2E-4.2 通过率 29/32 → 30/32（当时口径）。

### 缺陷 #13（P2）「流式问答」实际不流式 + 工具轮次耗尽静默返回空答案

- **现象**：库里常年有 3 个启用工具，导致 `stream_generate` 永远走「带工具」分支；该分支用**非流式** `ainvoke`，最后 `await on_token(full)` 只发**一个** token 事件 —— 前端「流式问答」退化为「等全部生成完再一次性显示」。另外工具循环 3 轮用尽后 `full = ""`，静默返回空答案。
- **根因**：工具分支为拿到结构化的 `tool_calls` 而统一采用非流式调用，未区分「工具轮」与「最终作答轮」。
- **修复**：抽出 `_stream_final(model)`；工具轮仍用非流式 `ainvoke`（拿 `tool_calls` 更可靠），**最终作答轮改用 `astream` 逐 token 推送**；模型确实无输出时回填占位串，保证 SSE 与落库一致；工具轮次耗尽时记录 warning 并改用直答兜底，不再返回空串。
- **验证**：E2E-7.4 事件序列出现连续多个 `token`（`token, token, token, …`），确认逐字流式恢复。

### 测试侧问题修正（非产品缺陷，一并披露）

| 编号 | 问题 | 性质 | 处理 |
|---|---|---|---|
| T1 | `harness.py` SSE 读取器**逐字节** `decode("utf-8","ignore")`，多字节中文被撕裂丢弃，token 只剩 ASCII 残渣（如 `'# [1][2]'`），导致 E2E-6.3 误判产品不一致 | 测试工具缺陷 | 改用 `codecs.getincrementaldecoder` 增量解码 |
| T2 | E2E-9.1 轮询退出条件把 `parsing` 当作已收敛状态，未等后台任务跑完就断言 | 测试用例缺陷 | 改为必须「全部进入终态（parsed/failed）」才退出 |
| T3 | D11 搜索 `被管理`，但 D2 已把该昵称改成 `改名后`，查的是不存在的历史昵称 | 测试数据维护 | 改用当前昵称 |
| T4 | D10 期望 `page=abc` 被静默容错，与路由 `page: int` 的显式校验冲突 | 期望与设计不符 | 经评估「显式拒绝优于静默兜底」，改以明确参数错误为期望 |
| T5 | `suite_e2e.py` 提取 `delta` 未做空值保护 | 健壮性 | 统一改为 `(e.get("delta") or "")` |

---

## 五、测试亮点与专项验证

### 5.1 混合检索量纲显式化（E2E-5.1）

验证六阶段 `StageTrace` 齐备，且**各阶段量纲与阈值适用性标注正确**——这是本项目最核心的设计亮点：

| 阶段 | 量纲 | 阈值适用 | 说明 |
|---|---|---|---|
| `rewrite` | none | 否 | 查询改写，不做召回 |
| `vector` | cosine | **是** | 余弦 0~1，可设阈值 |
| `bm25` | bm25 | **否** | 分数**无上界**，跨查询不可比，故不适用阈值 |
| `rrf` | rrf | **否** | 名次融合分（k=60），非相似度 |
| `backfill` | none | 否 | 父块回填，非召回 |
| `rerank` | rerank | **是** | 重排分 0~1，可设阈值 |

该设计避免了「拿 BM25 分数与余弦阈值硬比」这类经典缺陷。

### 5.2 BM25 通道兜底召回（E2E-5.3）

在默认严格阈值（cosine 0.30）下，向量通道被阈值过滤，**BM25 通道成功兜底**召回 2 条，最终上下文 1 条 —— 验证了双通道融合的容错价值。

### 5.3 LLM-as-judge 四指标评测（E2E-8.2 / 8.3）

| 指标 | 结果 | 实现要点 |
|---|---|---|
| Context Recall | 1.0 | **基于 `source_chunk_ids` 集合运算**，不依赖裁判模型，结果确定可复现 |
| Context Precision | 1.0 | 裁判模型逐条打分 |
| Faithfulness | 0.9 | 裁判 temperature=0 |
| Answer Relevancy | 0.9 | 裁判 temperature=0 |
| **综合** | **0.95** | |

### 5.4 Agentic RAG 工具调用闭环（E2E-7.6）

验证 Function Calling 完整闭环：模型发起 `calculator` 调用 → 执行 `123*(45+67)` → 工具结果回填 → 最终作答 `根据工具返回结果：123*(45+67) = 13776。`，工具调用日志落库 11 条。

### 5.5 安全测试（接口套件 K 组）

| 用例 | 结果 |
|---|---|
| SQL 注入 5 种载荷（`OR '1'='1'`、`DROP TABLE`、`UNION SELECT` 等） | 全部拒绝，无 token 泄漏 |
| 查询参数注入绕过 | 无法绕过参数化查询 |
| XSS 载荷入库 | 原样存储，不在后端执行（前端转义） |
| 上传文件名路径穿越（`../../evil.txt`） | 阻断，落盘被限制在 `/app/uploads/kb_<id>/` 下 |
| 参数类型攻击（`kb_id=abc`） | 被 Pydantic 校验拦截 |
| 超大 `page_size`（99999） | 截断至 200 |

### 5.6 契约一致性（接口套件 J1）

21 个核心接口全部返回统一 `{code, msg, data}` 结构；业务异常遵循「HTTP 200 + code≠0」约定，前端可统一处理。

---

## 六、结论

1. **测试覆盖**：143 条自动化用例全部通过（接口层 111、端到端 32），另含 42 文件 AST 静态检查。
2. **缺陷发现与修复**：本轮共定位并修复 **13 项产品缺陷**，其中 **3 项 P0**（文档入库 100% 失败、检索链路崩溃、Mock SSE 永久挂起）属阻断级，修复后端到端通过率由 **8/32 提升至 32/32**。
3. **代码质量改进**：
   - 修复 3 处「静默吞异常导致功能悄悄失效」（#1 自查节点、#9 异常不落库、#13 空答案）
   - 修复 2 处「异步任务生命周期错误」（#11 任务被 GC、#9 状态卡 running）
   - 修复 1 处「数据静默丢失」（#12 编辑被覆盖）
   - 修复 1 处「ORM 兼容性陷阱」（#4 MySQL `bulk_create` 不回填主键）
4. **设计合理性确认**：量纲显式化、双通道融合兜底、父子回块、Agentic 状态图收敛控制、统一返回契约等核心设计在实际运行中表现正确。
5. **测试资产**：`harness.py` / `static_check.py` / `suite_api.py` / `suite_e2e.py` 可重复执行（纯标准库，无第三方依赖），结果同时落 `results/api_results.json` 与 `results/e2e_results.json`，支持持续回归。

> 备注：所有缺陷均已修复并回归验证；测试侧自身问题（T1~T5）亦已修正，避免后续误判。

---

## 附录 A：原始测试数据

| 文件 | 内容 |
|---|---|
| `ai_system/tests/results/api_results.json` | 接口层 111 条用例的期望/实际/证据/结论 |
| `ai_system/tests/results/e2e_results.json` | 端到端 32 条用例的期望/实际/证据/结论 |

## 附录 B：复现方式

```bash
# 1. 启动沙箱（含 Mock 大模型）
cd ai_system
docker compose --profile test up -d --build

# 2. 冒烟检查 Mock 沙箱
curl http://127.0.0.1:8898/health

# 3. 执行测试（宿主机，仅需 Python 标准库）
cd tests
python static_check.py     # AST 静态检查
python suite_api.py        # 接口层 111 条
python suite_e2e.py        # 端到端 32 条
```
