"""检索策略：混合检索参数与分阶段阈值（阈值按量纲分开配）"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import KnowledgeBase, RetrievalStrategy, User

router = APIRouter(tags=["检索策略"])


class StrategyIn(BaseModel):
    name: str
    description: str = ""
    vector_top_k: int = 8
    bm25_top_k: int = 8
    rrf_k: int = 60
    use_rewrite: int = 1
    rewrite_mode: str = "multi_query"
    candidate_limit: int = 20
    cosine_threshold: float = 0.30
    rerank_enabled: int = 1
    rerank_top_n: int = 5
    rerank_threshold: float = 0.05
    max_retrieval: int = 2


@router.get("/retrievalStrategy/page")
async def page(query: str = Query(""), page: int = 1, page_size: int = 20, _: User = Depends(get_current_user)):
    qs = RetrievalStrategy.all()
    if query:
        qs = qs.filter(name__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    for it in items:
        it["kb_count"] = await KnowledgeBase.filter(retrieval_strategy_id=it["id"]).count()
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.get("/retrievalStrategy/options")
async def options(_: User = Depends(get_current_user)):
    return ok(await RetrievalStrategy.all().order_by("id").values("id", "name", "vector_top_k", "bm25_top_k", "rerank_enabled"))


@router.post("/retrievalStrategy")
async def create(body: StrategyIn, _: User = Depends(get_current_user)):
    if body.rewrite_mode not in ("multi_query", "hyde", "coref"):
        raise BizException("rewrite_mode 必须是 multi_query/hyde/coref")
    s = await RetrievalStrategy.create(**body.model_dump())
    return ok({"id": s.id})


@router.put("/retrievalStrategy/{sid}")
async def update(sid: int, body: StrategyIn, _: User = Depends(get_current_user)):
    s = await RetrievalStrategy.filter(id=sid).first()
    if not s:
        raise BizException("策略不存在")
    await s.update_from_dict(body.model_dump()).save()
    return ok()


@router.delete("/retrievalStrategy/{sid}")
async def remove(sid: int, _: User = Depends(get_current_user)):
    if await KnowledgeBase.filter(retrieval_strategy_id=sid).exists():
        raise BizException("该策略已被知识库绑定，先解绑再删除")
    s = await RetrievalStrategy.filter(id=sid).first()
    if s:
        await s.delete()
    return ok()
