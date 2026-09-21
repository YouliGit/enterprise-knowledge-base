"""切分策略：递归分块 / 父子分块"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import KnowledgeBase, SplitStrategy, User

router = APIRouter(tags=["切分策略"])


class StrategyIn(BaseModel):
    name: str
    mode: str = "parent_child"
    chunk_size: int = 500
    chunk_overlap: int = 50
    parent_chunk_size: int = 1500
    parent_chunk_overlap: int = 100
    separators_json: str = '["\\n\\n", "\\n", "。", "；", "，", " "]'
    remark: str = ""


@router.get("/splitStrategy/page")
async def page(query: str = Query(""), page: int = 1, page_size: int = 20, _: User = Depends(get_current_user)):
    qs = SplitStrategy.all()
    if query:
        qs = qs.filter(name__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    for it in items:
        it["kb_count"] = await KnowledgeBase.filter(split_strategy_id=it["id"]).count()
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.get("/splitStrategy/options")
async def options(_: User = Depends(get_current_user)):
    return ok(await SplitStrategy.all().order_by("id").values("id", "name", "mode", "chunk_size", "parent_chunk_size"))


@router.post("/splitStrategy")
async def create(body: StrategyIn, _: User = Depends(get_current_user)):
    if body.mode not in ("recursive", "parent_child"):
        raise BizException("mode 必须是 recursive/parent_child")
    s = await SplitStrategy.create(**body.model_dump())
    return ok({"id": s.id})


@router.put("/splitStrategy/{sid}")
async def update(sid: int, body: StrategyIn, _: User = Depends(get_current_user)):
    s = await SplitStrategy.filter(id=sid).first()
    if not s:
        raise BizException("策略不存在")
    await s.update_from_dict(body.model_dump()).save()
    return ok()


@router.delete("/splitStrategy/{sid}")
async def remove(sid: int, _: User = Depends(get_current_user)):
    if await KnowledgeBase.filter(split_strategy_id=sid).exists():
        raise BizException("该策略已被知识库绑定，先解绑再删除")
    s = await SplitStrategy.filter(id=sid).first()
    if s:
        await s.delete()
    return ok()
