"""检索测试 / 召回调试台（最多 4 套并排）"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from models import KnowledgeBase, RetrievalStrategy, RetrievalTestLog, User
from rag.retriever import retrieve_once

router = APIRouter(tags=["检索调试"])


class TestIn(BaseModel):
    kb_id: int
    query: str
    strategy_id: int | None = None
    with_answer: int = 0


class CompareIn(BaseModel):
    kb_id: int
    query: str
    strategy_ids: list[int] = []


@router.post("/retrieval/test")
async def test(body: TestIn, user: User = Depends(get_current_user)):
    """单次检索：返回分阶段追踪（量纲/阈值/命中）+ 最终上下文"""
    kb = await KnowledgeBase.filter(id=body.kb_id).first()
    if not kb:
        raise BizException("知识库不存在")
    strategy = None
    if body.strategy_id:
        strategy = await RetrievalStrategy.filter(id=body.strategy_id).first()
    if not strategy:
        strategy = await RetrievalStrategy.filter(id=kb.retrieval_strategy_id).first() or await RetrievalStrategy.first()
    if not strategy:
        raise BizException("尚未配置任何检索策略，请先到 管理端→检索策略 新增一套")
    out = await retrieve_once(kb, body.query, strategy)
    data = {
        "strategy": {"id": strategy.id, "name": strategy.name},
        "contexts": out.contexts_dict(),
        "traces": out.traces_dict(),
    }
    await RetrievalTestLog.create(
        kb_id=body.kb_id, query=body.query, strategy_id=strategy.id,
        result_json=str(out.contexts_dict())[:6000], cost_ms=sum(t.cost_ms for t in out.traces), user_id=user.id,
    )
    return ok(data)


@router.post("/retrieval/compare")
async def compare(body: CompareIn, user: User = Depends(get_current_user)):
    """召回调试台：最多 4 套策略并排对比"""
    if not body.strategy_ids:
        raise BizException("请选择要对比的检索策略")
    if len(body.strategy_ids) > 4:
        raise BizException("最多支持 4 套并排")
    kb = await KnowledgeBase.filter(id=body.kb_id).first()
    if not kb:
        raise BizException("知识库不存在")
    arms = []
    for sid in body.strategy_ids:
        strategy = await RetrievalStrategy.filter(id=sid).first()
        if not strategy:
            continue
        try:
            out = await retrieve_once(kb, body.query, strategy, with_rewrite=False)
            arms.append({
                "strategy": {"id": strategy.id, "name": strategy.name},
                "contexts": out.contexts_dict(),
                "traces": out.traces_dict(),
                "cost_ms": sum(t.cost_ms for t in out.traces),
            })
        except Exception as e:
            arms.append({"strategy": {"id": strategy.id, "name": strategy.name}, "error": str(e)})
    await RetrievalTestLog.create(
        kb_id=body.kb_id, query=body.query + " 【召回调试台】", strategy_id=0,
        result_json=str([a.get("contexts", []) for a in arms])[:6000],
        cost_ms=sum(a.get("cost_ms", 0) for a in arms),
        user_id=user.id,
    )
    return ok({"arms": arms})
