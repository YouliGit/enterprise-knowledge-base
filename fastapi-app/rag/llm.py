"""模型工厂：全部走阿里云百炼，配置存 MySQL，改配置立刻生效不用重启（带2秒缓存仅作降频）。

- 对话：qwen-plus          OpenAI 兼容
- 向量：text-embedding-v4  OpenAI 兼容，1024 维
- 重排：gte-rerank-v2      DashScope 原生（自写 LangChain 重排组件，见 rerank.py）
"""
import time

from common.exceptions import BizException
from models import AiModelConfig, PromptTemplate

import settings

_cache: dict = {}
_CACHE_TTL = 2.0


async def get_model_config(cfg_type: str, cfg_id: int | None = None) -> AiModelConfig:
    """读取启用的模型配置（cfg_id 指定时读指定配置）。"""
    key = f"cfg:{cfg_type}:{cfg_id}"
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    if cfg_id:
        cfg = await AiModelConfig.filter(id=cfg_id).first()
    else:
        cfg = await AiModelConfig.filter(type=cfg_type, enabled=1).order_by("-updated_at").first()
    if not cfg:
        raise BizException(f"缺少可用的「{cfg_type}」模型配置，请到 管理端→AI配置→AI模型配置 新增并启用")
    _cache[key] = (now, cfg)
    return cfg


def _resolve_base(cfg: AiModelConfig) -> str:
    return (cfg.api_base or "").strip() or settings.DASHSCOPE_OPENAI_BASE


def _resolve_key(cfg: AiModelConfig) -> str:
    return (cfg.api_key or "").strip() or settings.DASHSCOPE_API_KEY


async def get_chat_model(purpose: str = "chat", cfg_id: int | None = None, temperature: float | None = None):
    """对话模型（LangChain ChatOpenAI，指向百炼 OpenAI 兼容地址）。"""
    from langchain_openai import ChatOpenAI

    cfg = await get_model_config("chat", cfg_id)
    key = _resolve_key(cfg)
    if not key:
        raise BizException(f"模型配置「{cfg.name}」未填写 API Key")
    return ChatOpenAI(
        model=cfg.model,
        api_key=key,
        base_url=_resolve_base(cfg),
        temperature=cfg.temperature if temperature is None else temperature,
        streaming=purpose == "stream",
    )


async def get_judge_model():
    """裁判模型：temperature 固定为 0。"""
    return await get_chat_model(purpose="judge", temperature=0)


async def get_embedding_model(cfg_id: int | None = None):
    """向量模型：OpenAI 兼容 /embeddings，维度默认 1024。"""
    from langchain_openai import OpenAIEmbeddings

    cfg = await get_model_config("embedding", cfg_id)
    key = _resolve_key(cfg)
    if not key:
        raise BizException(f"模型配置「{cfg.name}」未填写 API Key")
    dim = cfg.dimension or settings.EMBEDDING_DIM
    return OpenAIEmbeddings(
        model=cfg.model,
        api_key=key,
        base_url=_resolve_base(cfg),
        dimensions=dim,
        check_embedding_ctx_length=False,
    ), dim


async def get_reranker(cfg_id: int | None = None):
    """重排组件：百炼原生接口，包成标准 BaseDocumentCompressor。"""
    from rag.rerank import DashScopeReranker

    cfg = await get_model_config("rerank", cfg_id)
    return DashScopeReranker(
        model=cfg.model,
        api_key=_resolve_key(cfg) or settings.DASHSCOPE_API_KEY,
        base_url=(cfg.api_base or "").strip() or settings.DASHSCOPE_NATIVE_BASE,
    )


# ---------------- Prompt 渲染 ----------------

async def get_prompt(code: str) -> tuple[str, int | None]:
    """取启用的模板内容；没有配置时回退内置兜底模板。返回 (content, id)。"""
    tpl = await PromptTemplate.filter(code=code, enabled=1).first()
    if tpl:
        return tpl.content, tpl.id
    return FALLBACK_PROMPTS.get(code, "{query}"), None


def render_prompt(content: str, **variables) -> str:
    """把 {variable} 占位符替换掉；未提供的占位符替换为空串。"""
    out = content
    for k, v in variables.items():
        out = out.replace("{" + k + "}", str(v if v is not None else ""))
    return out


FALLBACK_PROMPTS = {
    "qa_answer_concise": "你是企业知识库助手。请严格依据参考资料，用一段话简短回答问题。控制在80字以内。如果参考资料与问题无关，直接回答不知道。\n\n参考资料：\n{context}\n\n问题：{query}",
    "qa_answer_step": "你是企业知识库助手。若问题涉及操作流程或故障排查，请按「1. 2. 3.」给出步骤，每步一句话；否则正常简短回答。只依据参考资料。\n\n参考资料：\n{context}\n\n问题：{query}",
    "qa_answer_with_source": "你是企业知识库助手。请依据参考资料回答，并在每个关键结论后标注出处编号，如[1][2]。参考资料无关时回答不知道。\n\n参考资料：\n{context}\n\n问题：{query}",
    "rewrite_multi_query": "你是查询扩展器。把用户问题改写成3个不同表述的检索查询，覆盖同义词与相关说法，每行一个，不要解释。\n\n用户问题：{query}",
    "rewrite_coref": "你是查询改写器。结合对话历史，消解问题中的指代（它/这个/上面说的），输出一个独立完整的查询，不要解释。\n\n对话历史：\n{history}\n\n当前问题：{query}",
    "hyde_generate": "你是文档生成器。请直接写一段60字以内、可能包含问题答案的资料文本（不要回答问题本身，不要解释）。\n\n问题：{query}",
    "agent_evaluate_context": "你是检索质量评估器。判断参考资料是否足以回答问题。输出JSON：{\"sufficient\": true/false, \"reason\": \"一句话理由\", \"rewrite_hint\": \"不足时给改写建议\"}。\n\n问题：{query}\n\n参考资料（含相似度）：\n{context}",
    "agent_self_check": "你是答案质检器。判断答案是否严格依据参考资料、没有编造、且确实回答了问题。输出JSON：{\"pass\": true/false, \"reason\": \"一句话理由\"}。\n\n问题：{query}\n\n参考资料：\n{context}\n\n答案：{answer}",
    "judge_context_precision": "你是评测裁判。逐条判断下列检索片段对回答问题的有用程度，有用记1，无用记0。输出JSON：{\"scores\": [1,0,1]}。\n\n问题：{query}\n\n片段：\n{contexts}",
    "judge_faithfulness": "你是评测裁判。判断答案中的每个关键论断是否都能被参考资料支撑，被支撑的论断占全部论断的比例是多少。只输出一个0到1的小数，不要解释。\n\n参考资料：\n{context}\n\n答案：{answer}",
    "judge_answer_relevancy": "你是评测裁判。判断答案与问题的相关程度，跑题记0，完全切题记1。只输出一个0到1的小数，不要解释。\n\n问题：{query}\n\n答案：{answer}",
}
