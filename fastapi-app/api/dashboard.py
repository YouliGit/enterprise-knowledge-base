"""首页统计"""
from fastapi import APIRouter, Depends

from common.deps import get_current_user
from common.response import ok
from models import (
    AgentRun,
    AiModelConfig,
    ChatApp,
    ChatMessage,
    Chunk,
    Document,
    EvalRun,
    KnowledgeBase,
    User,
)
from rag import vectorstore

router = APIRouter(tags=["首页"])


@router.get("/dashboard/summary")
async def summary(_: User = Depends(get_current_user)):
    data = {
        "kb": await KnowledgeBase.all().count(),
        "doc": await Document.all().count(),
        "chunk": await Chunk.all().count(),
        "user": await User.all().count(),
        "app": await ChatApp.all().count(),
        "question": await ChatMessage.filter(role="user").count(),
        "agent_run": await AgentRun.all().count(),
        "optimize": await ChatMessage.filter(feedback="useless").count(),
        "vector": int(await vectorstore.vector_count() or 0),
        "model": await AiModelConfig.all().count(),
        "eval_run": await EvalRun.all().count(),
        "failed_doc": await Document.filter(status="failed").count(),
    }
    data["architecture"] = {
        "retriever": "向量 + BM25 + RRF 融合 + 重排 + 查询改写 + 父子回填",
        "chat_model": "qwen-plus（OpenAI 兼容）",
        "rerank_model": "gte-rerank-v2（DashScope 原生接口）",
        "judge": "LLM-as-judge 四指标，裁判 temperature=0",
        "decision": "LangGraph 状态图，检索轮次由模型判断",
        "embedding_model": "text-embedding-v4（1024维）",
        "vector_store": "PostgreSQL + PGVector",
        "scale": "余弦相似度 / BM25 / RRF名次分 / 重排相关分，阈值按量纲分开配",
    }
    return ok(data)
