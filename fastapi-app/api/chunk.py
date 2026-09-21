"""片段管理：人工修正后重新向量化 / 启停片段"""
import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page
from models import Chunk, Document, User
from rag.ingest import reembed_chunk
from rag import vectorstore

router = APIRouter(tags=["片段管理"])


class ChunkIn(BaseModel):
    content: str


@router.get("/chunk/page")
async def page(doc_id: int = Query(0), kb_id: int = Query(0), query: str = Query(""),
               only_child: int = Query(1), page: int = 1, page_size: int = 10,
               _: User = Depends(get_current_user)):
    qs = Chunk.all()
    if doc_id:
        qs = qs.filter(doc_id=doc_id)
    if kb_id:
        qs = qs.filter(kb_id=kb_id)
    if only_child == 1:
        qs = qs.filter(is_parent=0)
    if query:
        qs = qs.filter(content__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total = await qs.count()
    rows = await qs.offset(off).limit(ps).order_by("doc_id", "seq").values()
    doc_ids = {r["doc_id"] for r in rows}
    docs = {d.id: d.name for d in await Document.filter(id__in=list(doc_ids)).all()} if doc_ids else {}
    parent_ids = {r["parent_id"] for r in rows if r.get("parent_id")}
    parents = {c.id: c.content[:60] for c in await Chunk.filter(id__in=list(parent_ids)).all()} if parent_ids else {}
    out = []
    for r in rows:
        r["doc_name"] = docs.get(r["doc_id"], "")
        r["parent_preview"] = parents.get(r.get("parent_id"), "") if r.get("parent_id") else ""
        out.append(r)
    return ok({"list": out, "total": total, "page": p, "page_size": ps})


@router.put("/chunk/{cid}")
async def update(cid: int, body: ChunkIn, _: User = Depends(get_current_user)):
    """人工修正片段内容并重新向量化"""
    c = await Chunk.filter(id=cid).first()
    if not c:
        raise BizException("片段不存在")
    if not body.content.strip():
        raise BizException("内容不能为空")
    # 必须落库后再重新向量化：reembed_chunk 会重新读库，
    # 只改内存属性的话用户这次修改会被库里的旧内容覆盖掉（静默丢失编辑）。
    c.content = body.content
    c.char_len = len(body.content)
    await c.save()
    await reembed_chunk(cid)
    return ok()


@router.put("/chunk/{cid}/status")
async def set_status(cid: int, body: dict, _: User = Depends(get_current_user)):
    c = await Chunk.filter(id=cid).first()
    if not c:
        raise BizException("片段不存在")
    c.enabled = 1 if body.get("enabled") == 1 else 0
    await c.save()
    if c.enabled == 1:
        await reembed_chunk(cid)
    else:
        await vectorstore.delete_by_chunk_ids([cid])
    return ok()


@router.get("/chunk/{cid}")
async def detail(cid: int, _: User = Depends(get_current_user)):
    c = await Chunk.filter(id=cid).first()
    if not c:
        raise BizException("片段不存在")
    data = {"id": c.id, "doc_id": c.doc_id, "kb_id": c.kb_id, "parent_id": c.parent_id,
            "seq": c.seq, "content": c.content, "char_len": c.char_len, "is_parent": c.is_parent,
            "enabled": c.enabled}
    try:
        data["meta"] = json.loads(c.meta_json or "{}")
    except Exception:
        data["meta"] = {}
    return ok(data)
