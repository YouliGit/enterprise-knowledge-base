"""25 张业务表的 Tortoise ORM 模型（与 ai_system.sql 的 DDL 一一对应）。"""
from tortoise import fields
from tortoise.models import Model


class BaseModel(Model):
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        abstract = True


# 1 用户
class User(BaseModel):
    username = fields.CharField(max_length=64, unique=True, description="账号")
    password = fields.CharField(max_length=256, description="密码哈希")
    nickname = fields.CharField(max_length=64, default="", description="昵称")
    avatar = fields.CharField(max_length=512, default="", description="头像URL")
    email = fields.CharField(max_length=128, default="")
    phone = fields.CharField(max_length=32, default="")
    role = fields.CharField(max_length=16, default="user", description="admin/user")
    status = fields.IntField(default=1, description="1启用 0禁用")

    class Meta:
        table = "user"


# 2 AI模型配置
class AiModelConfig(BaseModel):
    name = fields.CharField(max_length=128, description="配置名称")
    type = fields.CharField(max_length=16, description="chat/embedding/rerank")
    model = fields.CharField(max_length=128, description="模型名")
    vendor = fields.CharField(max_length=32, default="dashscope", description="厂商")
    api_base = fields.CharField(max_length=512, default="", description="留空自动用百炼兼容地址")
    api_key = fields.CharField(max_length=512, default="", description="API Key")
    dimension = fields.IntField(default=0, description="向量维度，仅向量模型")
    temperature = fields.FloatField(default=0.7, description="温度，仅对话模型")
    enabled = fields.IntField(default=1, description="1启用 0停用")
    remark = fields.CharField(max_length=512, default="")
    test_info = fields.CharField(max_length=512, default="", description="最近一次连通性测试结果")

    class Meta:
        table = "ai_model_config"


# 3 Prompt模板
class PromptTemplate(BaseModel):
    code = fields.CharField(max_length=64, unique=True, description="编码")
    name = fields.CharField(max_length=128, description="名称")
    scene = fields.CharField(max_length=32, description="qa问答/rewrite改写/agent智能体/judge评测")
    content = fields.TextField(description="内容，支持 {variable} 占位符")
    enabled = fields.IntField(default=1)
    remark = fields.CharField(max_length=512, default="")

    class Meta:
        table = "prompt_template"


# 4 工具
class Tool(BaseModel):
    code = fields.CharField(max_length=64, unique=True)
    name = fields.CharField(max_length=128)
    description = fields.TextField(default="", description="给模型看的工具说明")
    schema_json = fields.TextField(default="{}", description="Function Calling JSON Schema")
    handler = fields.CharField(max_length=64, default="", description="内置处理器名")
    built_in = fields.IntField(default=0, description="1内置")
    enabled = fields.IntField(default=1)

    class Meta:
        table = "tool"


# 5 工具调用日志
class ToolCallLog(BaseModel):
    tool_id = fields.BigIntField(null=True)
    tool_code = fields.CharField(max_length=64, default="")
    agent_run_id = fields.BigIntField(null=True, description="关联Agent运行")
    args_json = fields.TextField(default="{}")
    result = fields.TextField(default="")
    status = fields.CharField(max_length=16, default="ok", description="ok/failed")
    cost_ms = fields.IntField(default=0)

    class Meta:
        table = "tool_call_log"


# 6 知识库
class KnowledgeBase(BaseModel):
    name = fields.CharField(max_length=128)
    description = fields.TextField(default="")
    vector_model_id = fields.BigIntField(null=True, description="绑定的向量模型配置")
    split_strategy_id = fields.BigIntField(null=True, description="绑定的切分策略")
    retrieval_strategy_id = fields.BigIntField(null=True, description="默认检索策略")
    owner_id = fields.BigIntField(null=True)
    status = fields.IntField(default=1)

    class Meta:
        table = "knowledge_base"


# 7 切分策略
class SplitStrategy(BaseModel):
    name = fields.CharField(max_length=128)
    mode = fields.CharField(max_length=16, default="parent_child", description="递归分块/父子分块")
    chunk_size = fields.IntField(default=500, description="子块大小(字符)")
    chunk_overlap = fields.IntField(default=50)
    parent_chunk_size = fields.IntField(default=1500, description="父块大小，父子分块时生效")
    parent_chunk_overlap = fields.IntField(default=100)
    separators_json = fields.TextField(default='["\\n\\n", "\\n", "。", "；", "，", " "]', description="递归分隔符")
    remark = fields.CharField(max_length=512, default="")

    class Meta:
        table = "split_strategy"


# 8 检索策略
class RetrievalStrategy(BaseModel):
    name = fields.CharField(max_length=128)
    description = fields.CharField(max_length=512, default="")
    vector_top_k = fields.IntField(default=8, description="向量召回数")
    bm25_top_k = fields.IntField(default=8, description="BM25召回数，0为关闭")
    rrf_k = fields.IntField(default=60, description="RRF 常数k")
    use_rewrite = fields.IntField(default=1, description="是否启用查询改写")
    rewrite_mode = fields.CharField(max_length=16, default="multi_query")
    candidate_limit = fields.IntField(default=20, description="重排候选上限")
    cosine_threshold = fields.FloatField(default=0.30, description="余弦相似度阈值(量纲0~1)")
    rerank_enabled = fields.IntField(default=1)
    rerank_top_n = fields.IntField(default=5, description="重排后保留数")
    rerank_threshold = fields.FloatField(default=0.05, description="重排相关分阈值(量纲0~1)")
    max_retrieval = fields.IntField(default=2, description="Agent 最大检索轮次上限")

    class Meta:
        table = "retrieval_strategy"


# 9 文档
class Document(BaseModel):
    kb_id = fields.BigIntField(index=True)
    name = fields.CharField(max_length=256)
    file_type = fields.CharField(max_length=16, default="", description="pdf/docx/xlsx/md/txt")
    file_size = fields.BigIntField(default=0)
    file_path = fields.CharField(max_length=512, default="")
    status = fields.CharField(max_length=16, default="pending")
    chunk_count = fields.IntField(default=0)
    error = fields.TextField(default="")

    class Meta:
        table = "document"


# 10 片段
class Chunk(BaseModel):
    doc_id = fields.BigIntField(index=True)
    kb_id = fields.BigIntField(index=True)
    parent_id = fields.BigIntField(null=True, index=True, description="父块ID，父子分块时子块指向父块")
    seq = fields.IntField(default=0)
    content = fields.TextField()
    char_len = fields.IntField(default=0)
    is_parent = fields.IntField(default=0, description="1父块 0子块")
    enabled = fields.IntField(default=1, description="人工修正可禁用某片段")
    meta_json = fields.TextField(default="{}")

    class Meta:
        table = "chunk"


# 11 检索测试日志
class RetrievalTestLog(BaseModel):
    kb_id = fields.BigIntField(index=True)
    query = fields.TextField()
    strategy_id = fields.BigIntField(null=True)
    result_json = fields.TextField(default="")
    cost_ms = fields.IntField(default=0)
    user_id = fields.BigIntField(null=True)

    class Meta:
        table = "retrieval_test_log"


# 12 问答应用
class ChatApp(BaseModel):
    name = fields.CharField(max_length=128)
    description = fields.TextField(default="")
    owner_id = fields.BigIntField(null=True)
    prompt_template_id = fields.BigIntField(null=True, description="问答Prompt模板")
    model_config_id = fields.BigIntField(null=True, description="对话模型配置")
    retrieval_strategy_id = fields.BigIntField(null=True)
    max_history = fields.IntField(default=3, description="携带历史轮数")
    show_ref = fields.IntField(default=1, description="是否展示引用来源")
    use_agent = fields.IntField(default=1, description="1走Agentic RAG状态图 0走单轮混合检索")
    enabled = fields.IntField(default=1)

    class Meta:
        table = "chat_app"


# 13 应用-知识库关联
class AppKbRel(BaseModel):
    app_id = fields.BigIntField(index=True)
    kb_id = fields.BigIntField(index=True)

    class Meta:
        table = "app_kb_rel"


# 14 会话
class ChatSession(BaseModel):
    app_id = fields.BigIntField(index=True)
    user_id = fields.BigIntField(index=True)
    title = fields.CharField(max_length=128, default="新会话")
    msg_count = fields.IntField(default=0)

    class Meta:
        table = "chat_session"


# 15 消息
class ChatMessage(BaseModel):
    session_id = fields.BigIntField(index=True)
    app_id = fields.BigIntField(default=0)
    user_id = fields.BigIntField(default=0)
    role = fields.CharField(max_length=16, description="user/assistant")
    content = fields.TextField()
    refs_json = fields.TextField(default="[]", description="引用来源片段")
    feedback = fields.CharField(max_length=16, default="", description="useful/useless/空")
    cost_ms = fields.IntField(default=0)
    agent_run_id = fields.BigIntField(null=True)

    class Meta:
        table = "chat_message"


# 16 Agent运行
class AgentRun(BaseModel):
    app_id = fields.BigIntField(default=0)
    session_id = fields.BigIntField(default=0)
    user_id = fields.BigIntField(default=0)
    query = fields.TextField()
    status = fields.CharField(max_length=16, default="running")
    rounds = fields.IntField(default=0, description="实际检索轮次")
    final_answer = fields.TextField(default="")
    total_cost_ms = fields.IntField(default=0)

    class Meta:
        table = "agent_run"


# 17 Agent步骤（时间线回放）
class AgentStep(BaseModel):
    run_id = fields.BigIntField(index=True)
    seq = fields.IntField(default=0)
    node = fields.CharField(max_length=32, description="节点：retrieve/evaluate/rewrite/generate/self_check/tool")
    action = fields.CharField(max_length=128, default="")
    thought = fields.TextField(default="", description="模型判断理由")
    input_json = fields.TextField(default="{}")
    output_json = fields.TextField(default="{}")
    status = fields.CharField(max_length=16, default="ok")
    cost_ms = fields.IntField(default=0)

    class Meta:
        table = "agent_step"


# 18 评测集
class EvalDataset(BaseModel):
    name = fields.CharField(max_length=128)
    description = fields.TextField(default="")
    kb_id = fields.BigIntField(null=True)
    owner_id = fields.BigIntField(null=True)

    class Meta:
        table = "eval_dataset"


# 19 评测用例
class EvalCase(BaseModel):
    dataset_id = fields.BigIntField(index=True)
    question = fields.TextField()
    ground_truth = fields.TextField(default="", description="参考答案")
    source_chunk_ids_json = fields.TextField(default="[]", description="来源片段ID，Context Recall 做集合运算用")

    class Meta:
        table = "eval_case"


# 20 评测运行
class EvalRun(BaseModel):
    dataset_id = fields.BigIntField()
    kb_id = fields.BigIntField()
    strategy_id = fields.BigIntField(null=True)
    report_name = fields.CharField(max_length=128, default="评测报告")
    status = fields.CharField(max_length=16, default="pending")
    case_count = fields.IntField(default=0)
    recall = fields.FloatField(default=0, description="Context Recall")
    precision = fields.FloatField(default=0, description="Context Precision")
    faithfulness = fields.FloatField(default=0, description="Faithfulness")
    relevancy = fields.FloatField(default=0, description="Answer Relevancy")
    overall = fields.FloatField(default=0, description="综合分")
    error = fields.TextField(default="")

    class Meta:
        table = "eval_run"


# 21 评测运行明细
class EvalRunItem(BaseModel):
    run_id = fields.BigIntField(index=True)
    case_id = fields.BigIntField()
    question = fields.TextField(default="")
    contexts_json = fields.TextField(default="[]", description="召回上下文")
    context_ids_json = fields.TextField(default="[]")
    answer = fields.TextField(default="")
    recall = fields.FloatField(default=0)
    precision = fields.FloatField(default=0)
    faithfulness = fields.FloatField(default=0)
    relevancy = fields.FloatField(default=0)
    overall = fields.FloatField(default=0)
    detail_json = fields.TextField(default="{}")

    class Meta:
        table = "eval_run_item"


# 22 策略对比运行
class CompareRun(BaseModel):
    name = fields.CharField(max_length=128, default="策略对比")
    kb_id = fields.BigIntField()
    dataset_id = fields.BigIntField()
    status = fields.CharField(max_length=16, default="pending")
    arm_count = fields.IntField(default=0)
    error = fields.TextField(default="")

    class Meta:
        table = "compare_run"


# 23 策略对比臂
class CompareArm(BaseModel):
    run_id = fields.BigIntField(index=True)
    arm_index = fields.IntField(default=0, description="0~3，最多4套并排")
    strategy_id = fields.BigIntField(null=True)
    strategy_name = fields.CharField(max_length=128, default="")
    recall = fields.FloatField(default=0)
    precision = fields.FloatField(default=0)
    faithfulness = fields.FloatField(default=0)
    relevancy = fields.FloatField(default=0)
    overall = fields.FloatField(default=0)
    avg_cost_ms = fields.IntField(default=0)

    class Meta:
        table = "compare_arm"


# 24 操作日志
class OperationLog(BaseModel):
    user_id = fields.BigIntField(null=True)
    username = fields.CharField(max_length=64, default="")
    action = fields.CharField(max_length=128, default="")
    detail = fields.TextField(default="")
    ip = fields.CharField(max_length=64, default="")

    class Meta:
        table = "operation_log"


# 25 系统配置
class SysConfig(BaseModel):
    key = fields.CharField(max_length=64, unique=True)
    value = fields.TextField(default="")
    remark = fields.CharField(max_length=256, default="")

    class Meta:
        table = "sys_config"


ALL_MODELS = [
    User, AiModelConfig, PromptTemplate, Tool, ToolCallLog,
    KnowledgeBase, SplitStrategy, RetrievalStrategy, Document, Chunk,
    RetrievalTestLog, ChatApp, AppKbRel, ChatSession, ChatMessage,
    AgentRun, AgentStep, EvalDataset, EvalCase, EvalRun,
    EvalRunItem, CompareRun, CompareArm, OperationLog, SysConfig,
]
