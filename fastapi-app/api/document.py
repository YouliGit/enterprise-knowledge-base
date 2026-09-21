"""文档管理：上传解析 / 重新解析 / 删除"""
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import Chunk, Document, KnowledgeBase, User
from rag import vectorstore
from rag.ingest import reparse_document
from rag.parser import sniff_file_type
from rag.retriever import invalidate_bm25_cache

import settings

router = APIRouter(tags=["文档管理"])

ALLOWED = {"pdf", "docx", "doc", "xlsx", "xls", "md", "txt", "csv"}


@router.post("/document/upload")
async def upload(kb_id: int = Form(...), file: UploadFile = File(...), _: User = Depends(get_current_user)):
    kb = await KnowledgeBase.filter(id=kb_id).first()
    if not kb:
        raise BizException("知识库不存在")
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")
    if suffix not in ALLOWED:
        raise BizException(f"不支持的文件类型 .{suffix}，仅支持 {', '.join(sorted(ALLOWED))}")
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise BizException("文件不能超过50MB")
    ftype = sniff_file_type(file.filename or "")
    save_dir = Path(settings.UPLOAD_DIR) / f"kb_{kb_id}"
    save_dir.mkdir(parents=True, exist_ok=True)
    save_name = f"{int(time.time() * 1000)}_{Path(file.filename).name}"
    save_path = save_dir / save_name
    save_path.write_bytes(content)
    doc = await Document.create(
        kb_id=kb_id, name=file.filename, file_type=ftype,
        file_size=len(content), file_path=str(save_path), status="pending",
    )
    from rag.ingest import spawn_ingest

    spawn_ingest(doc.id)
    return ok({"id": doc.id, "msg": "已提交解析，稍后刷新查看状态"})


@router.get("/document/page")
async def page(kb_id: int = Query(0), query: str = Query(""), page: int = 1, page_size: int = 10,
               _: User = Depends(get_current_user)):
    qs = Document.all()
    if kb_id:
        qs = qs.filter(kb_id=kb_id)
    if query:
        qs = qs.filter(name__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.post("/document/{doc_id}/reparse")
async def reparse(doc_id: int, _: User = Depends(get_current_user)):
    doc = await Document.filter(id=doc_id).first()
    if not doc:
        raise BizException("文档不存在")
    await reparse_document(doc_id)
    return ok({"msg": "已重新解析"})


@router.delete("/document/{doc_id}")
async def remove(doc_id: int, _: User = Depends(get_current_user)):
    doc = await Document.filter(id=doc_id).first()
    if not doc:
        raise BizException("文档不存在")
    if doc.file_path:
        Path(doc.file_path).unlink(missing_ok=True)
    await vectorstore.delete_by_doc(doc_id)
    await Chunk.filter(doc_id=doc_id).delete()
    invalidate_bm25_cache(doc.kb_id)
    await doc.delete()
    return ok()


@router.post("/document/batch_delete")
async def batch_delete(body: dict, _: User = Depends(get_current_user)):
    ids = [int(x) for x in (body.get("ids") or [])]
    for doc_id in ids:
        doc = await Document.filter(id=doc_id).first()
        if not doc:
            continue
        if doc.file_path:
            Path(doc.file_path).unlink(missing_ok=True)
        await vectorstore.delete_by_doc(doc_id)
        await Chunk.filter(doc_id=doc_id).delete()
        invalidate_bm25_cache(doc.kb_id)
        await doc.delete()
    return ok({"deleted": len(ids)})
