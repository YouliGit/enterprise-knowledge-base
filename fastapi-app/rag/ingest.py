"""文档入库管道：解析 → 切分 → 片段落库 → 子块向量化入 PGVector → 更新统计。

父子分块：只把子块向量化参与检索（小块用来找），命中后回填整个父块给模型生成（大块用来答）。
"""
import asyncio
import json
import time

from models import Chunk, Document, KnowledgeBase, RetrievalStrategy, SplitStrategy
from rag import vectorstore
from rag.parser import parse_file, sniff_file_type
from rag.retriever import invalidate_bm25_cache
from rag.splitter import split_by_strategy


async def _embed_texts(texts: list[str], batch: int = 16) -> list[list[float]]:
    from rag.llm import get_embedding_model

    model, dim = await get_embedding_model()
    vecs: list[list[float]] = []
    for i in range(0, len(texts), batch):
        part = await model.aembed_documents(texts[i:i + batch])
        for v in part:
            if len(v) != dim:
                raise RuntimeError(f"向量维度不符：模型返回 {len(v)} 维，向量库为 {dim} 维，请核对模型配置的维度")
        vecs.extend(part)
    return vecs


async def _fetch_ids(doc_id: int, is_parent: int, expect: int) -> list[int]:
    """回查某个文档本次入库的片段 id（按 seq 升序）。

    MySQL 下 Tortoise 的 bulk_create 不会回填自增主键（PostgreSQL 才支持 RETURNING），
    因此必须回查一次，否则会拿到一堆 None，导致：
      - 子块 parent_id 丢失 → 父子回填失效
      - 向量入库 chunk_id=NULL → PGVector NOT NULL 约束报错，文档永远解析失败
    """
    rows = await Chunk.filter(doc_id=doc_id, is_parent=is_parent).order_by("seq").values("id", "seq")
    # 同一文档重新解析时旧数据已清理，这里按 seq 取最新 expect 条即可
    ids = [r["id"] for r in rows[-expect:]] if expect else []
    if len(ids) != expect:
        raise RuntimeError(f"片段主键回查异常：期望 {expect} 条，实际 {len(ids)} 条（doc_id={doc_id}）")
    return ids


async def ingest_document(doc_id: int):
    """后台任务：单个文档完整入库。"""
    doc = await Document.filter(id=doc_id).first()
    if not doc:
        return
    kb = await KnowledgeBase.filter(id=doc.kb_id).first()
    if not kb:
        doc.status = "failed"
        doc.error = "知识库不存在"
        await doc.save()
        return
    doc.status = "parsing"
    doc.error = ""
    await doc.save()
    t0 = time.time()
    try:
        text = parse_file(doc.file_path, doc.file_type or sniff_file_type(doc.name))
        if not (text or "").strip():
            raise RuntimeError("解析结果为空（可能是扫描件，需要OCR）")

        # 旧数据清理（重新解析场景）
        old_chunks = await Chunk.filter(doc_id=doc.id).values_list("id", flat=True)
        await vectorstore.delete_by_chunk_ids(list(old_chunks))
        await Chunk.filter(doc_id=doc.id).delete()

        strategy = None
        if kb.split_strategy_id:
            strategy = await SplitStrategy.filter(id=kb.split_strategy_id).first()
        if not strategy:
            strategy = await SplitStrategy.first()
        if not strategy:
            strategy = await SplitStrategy.create(name="默认父子分块", mode="parent_child", chunk_size=500,
                                                  chunk_overlap=50, parent_chunk_size=1500, parent_chunk_overlap=100)

        result = split_by_strategy(text, strategy)
        parents: list[str] = result["parents"]
        children: list[dict] = result["children"]

        # 父块入库
        parent_rows = []
        if parents:
            parent_rows = [
                Chunk(doc_id=doc.id, kb_id=kb.id, parent_id=None, seq=i, content=p,
                      char_len=len(p), is_parent=1, meta_json="{}")
                for i, p in enumerate(parents)
            ]
            await Chunk.bulk_create(parent_rows)
            # MySQL 下 bulk_create 不回填自增主键，需回查（按 doc_id+is_parent+seq 唯一定位）
            parent_id_list = await _fetch_ids(doc.id, 1, len(parent_rows))
        else:
            parent_id_list = []

        # 子块入库（parent_child 模式指向父块；recursive 模式无父块）
        # 先确定每个子块应挂的父块 id，再入库（避免依赖 bulk_create 回填主键）
        child_parent_ids = []
        for c in children:
            pi = c.get("parent_index", -1)
            pid = parent_id_list[pi] if 0 <= pi < len(parent_id_list) else None
            child_parent_ids.append(pid)
        child_rows = [
            Chunk(doc_id=doc.id, kb_id=kb.id, parent_id=child_parent_ids[i], seq=i, content=c["content"],
                  char_len=len(c["content"]), is_parent=0, meta_json="{}")
            for i, c in enumerate(children)
        ]
        if child_rows:
            await Chunk.bulk_create(child_rows)
            child_id_list = await _fetch_ids(doc.id, 0, len(child_rows))
        else:
            child_id_list = []

        # 只向量化子块
        texts = [c.content for c in child_rows]
        if not texts:
            raise RuntimeError("切分结果为空")
        vectors = await _embed_texts(texts)
        rows = []
        for idx, (c, v) in enumerate(zip(child_rows, vectors)):
            rows.append({
                "chunk_id": child_id_list[idx], "doc_id": doc.id, "kb_id": kb.id,
                "content": c.content, "embedding": v,
                "meta": {"doc": doc.name, "seq": c.seq, "parent_id": c.parent_id or 0},
            })
        await vectorstore.upsert_vectors(rows)

        doc.status = "parsed"
        doc.chunk_count = len(child_rows)
        await doc.save()
        invalidate_bm25_cache(kb.id)
    except Exception as e:
        doc.status = "failed"
        doc.error = f"{type(e).__name__}: {e}"
        await doc.save()
    return


async def reparse_document(doc_id: int):
    """重新解析入口"""
    return await ingest_document(doc_id)


async def rebuild_kb_index(kb_id: int):
    """重建索引：向量模型/维度变更后，对库内全部启用子块重新向量化。"""
    kb = await KnowledgeBase.filter(id=kb_id).first()
    if not kb:
        return
    chunks = await Chunk.filter(kb_id=kb_id, enabled=1, is_parent=0).all()
    texts = [c.content for c in chunks]
    t0 = time.time()
    if not texts:
        await vectorstore.delete_by_kb(kb_id)
        return
    vectors = await _embed_texts(texts)
    rows = []
    for c, v in zip(chunks, vectors):
        meta = {}
        try:
            meta = json.loads(c.meta_json or "{}")
        except Exception:
            pass
        rows.append({
            "chunk_id": c.id, "doc_id": c.doc_id, "kb_id": kb_id,
            "content": c.content, "embedding": v, "meta": meta,
        })
    await vectorstore.delete_by_kb(kb_id)
    for i in range(0, len(rows), 200):
        await vectorstore.upsert_vectors(rows[i:i + 200])
    invalidate_bm25_cache(kb_id)
    return {"chunks": len(rows), "cost_ms": int((time.time() - t0) * 1000)}


async def reembed_chunk(chunk_id: int):
    """片段人工修正后重新向量化（含其父块引用关系保持不变）

    注意：本函数以库中最新内容为准。调用方如需修改内容，必须先把改动 save 落库，
    否则这里读到的仍是旧内容，会把这次人工修正覆盖回去。
    父块不参与向量检索（大块用来答），此处只同步 char_len。
    """
    c = await Chunk.filter(id=chunk_id).first()
    if not c:
        return
    if c.is_parent == 1:
        if c.char_len != len(c.content or ""):
            c.char_len = len(c.content or "")
            await c.save()
        return
    c.char_len = len(c.content or "")
    await c.save()
    vecs = await _embed_texts([c.content])
    await vectorstore.upsert_vectors([{
        "chunk_id": c.id, "doc_id": c.doc_id, "kb_id": c.kb_id, "content": c.content,
        "embedding": vecs[0], "meta": {"parent_id": c.parent_id or 0, "seq": c.seq},
    }])
    invalidate_bm25_cache(c.kb_id)


# 后台解析任务的强引用集合。
# asyncio 事件循环对 task 只持弱引用，若创建后不保存引用，任务可能在执行途中被 GC 回收，
# 表现为并发上传时文档永远停在 pending/parsing。这里显式持有，完成后自行摘除。
_BG_TASKS: set[asyncio.Task] = set()


def spawn_ingest(doc_id: int):
    """Fire-and-forget 后台解析任务（持有强引用，避免任务被 GC 打断）"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    task = loop.create_task(_run_ingest_safe(doc_id))
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)
    return task


async def _run_ingest_safe(doc_id: int):
    """包装后台解析：任何未捕获异常都落成文档 failed，避免文档永远卡在中间态。"""
    try:
        await ingest_document(doc_id)
    except Exception as e:  # ingest_document 内部已兜底，这里是最后一道防线
        try:
            doc = await Document.filter(id=doc_id).first()
            if doc and doc.status not in ("parsed", "failed"):
                doc.status = "failed"
                doc.error = f"{type(e).__name__}: {e}"[:1000]
                await doc.save()
        except Exception:
            pass
