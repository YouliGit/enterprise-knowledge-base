"""知识库管理：新建绑定向量模型与切分策略、重建索引、批量删除"""
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import AiModelConfig, Chunk, Document, KnowledgeBase, RetrievalStrategy, SplitStrategy, User
from rag import vectorstore
from rag.ingest import rebuild_kb_index
from rag.retriever import invalidate_bm25_cache

router = APIRouter(tags=["知识库"])


class KbIn(BaseModel):
    name: str
    description: str = ""
    vector_model_id: int | None = None
    split_strategy_id: int | None = None
    retrieval_strategy_id: int | None = None


async def _attach_stats(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["doc_count"] = await Document.filter(kb_id=r["id"]).count()
        r["chunk_count"] = await Chunk.filter(kb_id=r["id"], is_parent=0).count()
        r["vector_count"] = int(await vectorstore.vector_count(r["id"]) or 0)
        if r.get("vector_model_id"):
            m = await AiModelConfig.filter(id=r["vector_model_id"]).first()
            r["vector_model_name"] = m.model if m else ""
        else:
            r["vector_model_name"] = ""
        if r.get("split_strategy_id"):
            s = await SplitStrategy.filter(id=r["split_strategy_id"]).first()
            r["split_strategy_name"] = s.name if s else ""
        else:
            r["split_strategy_name"] = ""
    return rows


@router.get("/knowledgeBase/page")
async def page(query: str = Query(""), page: int = 1, page_size: int = 10, _: User = Depends(get_current_user)):
    qs = KnowledgeBase.all()
    if query:
        qs = qs.filter(name__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    await _attach_stats(items)
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.get("/knowledgeBase/options")
async def options(_: User = Depends(get_current_user)):
    rows = await KnowledgeBase.filter(status=1).order_by("id").values("id", "name")
    return ok(rows)


@router.post("/knowledgeBase")
async def create(body: KbIn, user: User = Depends(get_current_user)):
    if not body.name.strip():
        raise BizException("名称不能为空")
    if not body.vector_model_id:
        raise BizException("请选择向量模型")
    kb = await KnowledgeBase.create(owner_id=user.id, **body.model_dump())
    return ok({"id": kb.id})


@router.put("/knowledgeBase/{kid}")
async def update(kid: int, body: KbIn, _: User = Depends(get_current_user)):
    kb = await KnowledgeBase.filter(id=kid).first()
    if not kb:
        raise BizException("知识库不存在")
    old_vec = kb.vector_model_id
    await kb.update_from_dict(body.model_dump()).save()
    if old_vec != body.vector_model_id:
        # 向量模型变了，索引需要重建
        import asyncio

        asyncio.get_event_loop().create_task(rebuild_kb_index(kid))
    return ok()


@router.delete("/knowledgeBase/{kid}")
async def remove(kid: int, _: User = Depends(get_current_user)):
    kb = await KnowledgeBase.filter(id=kid).first()
    if not kb:
        raise BizException("知识库不存在")
    for doc in await Document.filter(kb_id=kid).all():
        if doc.file_path:
            Path(doc.file_path).unlink(missing_ok=True)
        await doc.delete()
    await Chunk.filter(kb_id=kid).delete()
    await vectorstore.delete_by_kb(kid)
    invalidate_bm25_cache(kid)
    await kb.delete()
    return ok()


@router.post("/knowledgeBase/batch_delete")
async def batch_delete(body: dict, _: User = Depends(get_current_user)):
    ids = [int(x) for x in (body.get("ids") or [])]
    for kid in ids:
        kb = await KnowledgeBase.filter(id=kid).first()
        if not kb:
            continue
        for doc in await Document.filter(kb_id=kid).all():
            if doc.file_path:
                Path(doc.file_path).unlink(missing_ok=True)
            await doc.delete()
        await Chunk.filter(kb_id=kid).delete()
        await vectorstore.delete_by_kb(kid)
        invalidate_bm25_cache(kid)
        await kb.delete()
    return ok({"deleted": len(ids)})


@router.post("/knowledgeBase/{kid}/rebuild")
async def rebuild(kid: int, _: User = Depends(get_current_user)):
    """重建索引：向量模型/维度变更后全量重嵌入"""
    kb = await KnowledgeBase.filter(id=kid).first()
    if not kb:
        raise BizException("知识库不存在")
    import asyncio

    task = asyncio.get_event_loop().create_task(rebuild_kb_index(kid))
    return ok({"msg": "重建任务已启动", "hint": "可稍后刷新查看向量数"})


@router.get("/knowledgeBase/{kid}/rebuild_status")
async def rebuild_status(kid: int, _: User = Depends(get_current_user)):
    return ok({"vector_count": int(await vectorstore.vector_count(kid) or 0),
               "chunk_count": await Chunk.filter(kb_id=kid, is_parent=0, enabled=1).count()})
