"""混合检索主管道（分阶段追踪 + 量纲显式化）。

流程：查询改写 → 向量召回(余弦,阈值过滤) ∥ BM25召回(无上界,不过滤)
     → RRF 名次融合(不适用阈值) → 父子回填(小块用来找,大块用来答) → 重排(相关分,阈值过滤)
每一步落 StageTrace：查询词、量纲、阈值与是否适用、命中明细，前端完整回放。
"""
import time

from models import Chunk, KnowledgeBase, RetrievalStrategy
from rag.bm25 import BM25Index
from rag.fusion import dedupe_keep_score, rrf_fuse
from rag.llm import get_embedding_model, get_reranker
from rag.rewrite import coref_resolve, hyde_document, multi_query_expand
from rag.schemas import (
    SCALE_BM25,
    SCALE_COSINE,
    SCALE_RERANK,
    SCALE_RRF,
    Hit,
    RetrievalOutput,
    RetrievedContext,
    StageTrace,
)

# BM25 索引进程内缓存：{kb_id: (chunk_ids, index)}，片段人工修正/重建索引时失效
_bm25_cache: dict[int, tuple[list[int], BM25Index]] = {}


def invalidate_bm25_cache(kb_id: int | None = None):
    if kb_id is None:
        _bm25_cache.clear()
    else:
        _bm25_cache.pop(kb_id, None)


async def _load_children(kb_id: int):
    """加载知识库全部启用子块（递归模式下 is_parent=0 的块即最终块）。"""
    rows = (
        await Chunk.filter(kb_id=kb_id, enabled=1, is_parent=0)
        .order_by("doc_id", "seq")
        .values("id", "parent_id", "content")
    )
    return rows


async def _get_bm25(kb_id: int) -> tuple[list[int], BM25Index]:
    hit = _bm25_cache.get(kb_id)
    if hit:
        return hit[0], hit[1]
    rows = await _load_children(kb_id)
    ids = [r["id"] for r in rows]
    index = BM25Index(ids, [r["content"] for r in rows])
    _bm25_cache[kb_id] = (ids, index)
    return ids, index


async def _vector_stage(kb_id: int, queries: list[str], strategy: RetrievalStrategy, traces: list) -> tuple[dict[int, float], dict[int, str]]:
    """向量召回：余弦相似度 0~1，按量纲阈值过滤。返回 ({chunk_id: max_cosine}, {chunk_id: content})"""
    t0 = time.time()
    emb_model, _dim = await get_embedding_model()
    docs = await emb_model.aembed_documents(queries)  # 批量向量
    merged: dict[int, float] = {}
    contents: dict[int, str] = {}
    for emb in docs:
        for r in await _vector_search_one(kb_id, emb, strategy.vector_top_k):
            if r["score"] > merged.get(r["chunk_id"], -1):
                merged[r["chunk_id"]] = r["score"]
                contents[r["chunk_id"]] = r["content"]
    # 按量纲阈值过滤（余弦相似度：是）
    thr = strategy.cosine_threshold
    passed = {cid: s for cid, s in merged.items() if s >= thr}
    trace = StageTrace(
        stage="vector",
        query=" | ".join(queries),
        scale=SCALE_COSINE,
        threshold=thr,
        threshold_applies=True,
        note=f"{len(queries)}条查询×top{strategy.vector_top_k}，{len(merged)}命中，阈值{thr}过滤后{len(passed)}",
        cost_ms=int((time.time() - t0) * 1000),
    )
    trace.hits = [
        Hit(chunk_id=cid, parent_id=None, content=contents[cid], score=s, scale=SCALE_COSINE, rank=i + 1).to_dict()
        for i, (cid, s) in enumerate(sorted(merged.items(), key=lambda x: x[1], reverse=True)[:20])
    ]
    traces.append(trace)
    return passed, contents


async def _vector_search_one(kb_id: int, embedding: list[float], top_k: int):
    from rag import vectorstore

    return await vectorstore.vector_search(kb_id, embedding, top_k)


async def _bm25_stage(kb_id: int, queries: list[str], strategy: RetrievalStrategy, traces: list) -> dict[int, float]:
    """BM25 召回：分数无上界，不做阈值过滤。"""
    t0 = time.time()
    ids, index = await _get_bm25(kb_id)
    id_set = set(ids)
    merged: dict[int, float] = {}
    for q in queries:
        for cid, s in index.search(q, strategy.bm25_top_k):
            if cid in id_set and s > merged.get(cid, -1):
                merged[cid] = s
    trace = StageTrace(
        stage="bm25",
        query=" | ".join(queries),
        scale=SCALE_BM25,
        threshold=None,
        threshold_applies=False,
        note=f"jieba分词{len(queries)}条查询×top{strategy.bm25_top_k}，{len(merged)}命中；分数无上界，本次不适用阈值",
        cost_ms=int((time.time() - t0) * 1000),
    )
    trace.hits = [
        Hit(chunk_id=cid, parent_id=None, content="", score=s, scale=SCALE_BM25, rank=i + 1).to_dict(preview=0)
        for i, (cid, s) in enumerate(sorted(merged.items(), key=lambda x: x[1], reverse=True)[:20])
    ]
    traces.append(trace)
    return merged


def _rrf_stage(vec_scores: dict[int, float], bm25_scores: dict[int, float], strategy: RetrievalStrategy, traces: list) -> list[int]:
    """RRF 名次融合：只看名次不看分数（余弦0~1 与 BM25 无上界量纲不可比）。"""
    t0 = time.time()
    vec_rank = [cid for cid, _ in sorted(vec_scores.items(), key=lambda x: x[1], reverse=True)]
    bm25_rank = [cid for cid, _ in sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)]
    fused = rrf_fuse([r for r in (vec_rank, bm25_rank) if r], k=strategy.rrf_k or 60)
    trace = StageTrace(
        stage="rrf",
        query="",
        scale=SCALE_RRF,
        threshold=None,
        threshold_applies=False,
        note=f"两路名次融合 k={strategy.rrf_k}，{len(fused)}候选；名次分约0.016~0.033，本次不适用阈值",
        cost_ms=int((time.time() - t0) * 1000),
    )
    trace.hits = [
        Hit(chunk_id=cid, parent_id=None, content="", score=s, scale=SCALE_RRF, rank=i + 1).to_dict(preview=0)
        for i, (cid, s) in enumerate(list(fused.items())[:20])
    ]
    traces.append(trace)
    return fused


async def _backfill_stage(kb_id: int, candidate_ids: list[int], fused_map: dict[int, float], vec_map: dict[int, float],
                          strategy: RetrievalStrategy, traces: list):
    """父子回填：命中的子块 → 回填整个父块（大块用来答）。递归分块时父块即子块本身。"""
    t0 = time.time()
    ids = candidate_ids[: strategy.candidate_limit or 20]
    children = await Chunk.filter(id__in=ids).values("id", "parent_id", "content")
    child_map = {c["id"]: c for c in children}
    parent_ids: dict[int, int] = {}
    for cid in ids:
        c = child_map.get(cid)
        if not c:
            continue
        pid = c["parent_id"] or c["id"]
        parent_ids[pid] = pid
    parents = await Chunk.filter(id__in=list(parent_ids.keys())).values("id", "content") if parent_ids else []
    parent_content = {p["id"]: p["content"] for p in parents}
    # 父块得分 = 其子块最高 RRF 分
    parent_score: dict[int, float] = {}
    for cid in ids:
        c = child_map.get(cid)
        if not c:
            continue
        pid = c["parent_id"] or c["id"]
        s = fused_map.get(cid, 0.0)
        if s > parent_score.get(pid, -1):
            parent_score[pid] = s
    trace = StageTrace(
        stage="backfill",
        query="",
        scale="none",
        threshold=None,
        threshold_applies=False,
        note=f"{len(ids)}子块候选回填为{len(parent_content)}个父块（小块用来找，大块用来答）",
        cost_ms=int((time.time() - t0) * 1000),
    )
    trace.hits = [
        Hit(chunk_id=pid, parent_id=pid, content=parent_content.get(pid, ""), score=s, scale=SCALE_RRF, rank=i + 1).to_dict()
        for i, (pid, s) in enumerate(sorted(parent_score.items(), key=lambda x: x[1], reverse=True))
    ]
    traces.append(trace)
    # 父块各自的向量最高分（展示用）
    child_ids_by_parent: dict[int, list[int]] = {}
    for cid in ids:
        c = child_map.get(cid)
        if c:
            child_ids_by_parent.setdefault(c["parent_id"] or c["id"], []).append(cid)
    parent_vec = {}
    for pid, cids in child_ids_by_parent.items():
        vals = [vec_map[c] for c in cids if c in vec_map]
        parent_vec[pid] = max(vals) if vals else None
    return parent_score, parent_content, parent_vec


async def _rerank_stage(query: str, parent_ids: list[int], parent_content: dict[int, str],
                        strategy: RetrievalStrategy, traces: list) -> dict[int, float]:
    """重排：粗筛之后执行，候选上限 20 条；相关分 0~1，按量纲阈值过滤。"""
    trace = StageTrace(stage="rerank", query=query, scale=SCALE_RERANK,
                       threshold=strategy.rerank_threshold, threshold_applies=True)
    if not strategy.rerank_enabled:
        trace.note = "策略未启用重排"
        trace.cost_ms = 0
        traces.append(trace)
        return {pid: -1.0 for pid in parent_ids}
    t0 = time.time()
    texts = [parent_content.get(pid, "") for pid in parent_ids]
    scores: dict[int, float] = {}
    try:
        reranker = await get_reranker()
        results = await reranker.rerank_texts(query, texts, top_n=len(texts))
        for r in results:
            pid = parent_ids[r["index"]]
            scores[pid] = r["relevance_score"]
        thr = strategy.rerank_threshold
        kept = {pid: s for pid, s in scores.items() if s >= thr}
        top = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[: strategy.rerank_top_n or 5])
        final = {pid: s for pid, s in scores.items() if pid in top and s >= thr}
        trace.note = f"重排{len(texts)}条候选，阈值{thr}过滤后保留{len(final)}条"
        trace.hits = [
            Hit(chunk_id=pid, parent_id=pid, content=parent_content.get(pid, ""), score=s, scale=SCALE_RERANK, rank=i + 1).to_dict()
            for i, (pid, s) in enumerate(sorted(scores.items(), key=lambda x: x[1], reverse=True))
        ]
        trace.cost_ms = int((time.time() - t0) * 1000)
        traces.append(trace)
        return final
    except Exception as e:
        trace.note = f"重排失败降级为未重排: {e}"
        trace.cost_ms = int((time.time() - t0) * 1000)
        traces.append(trace)
        return {pid: -1.0 for pid in parent_ids}


async def _rewrite_stage(query: str, strategy: RetrievalStrategy, history: list[dict] | None, traces: list, round_no: int, hint: str = "") -> list[str]:
    """查询改写：多查询扩展 / HyDE / 指代消解。返回改写后的查询组。"""
    t0 = time.time()
    queries = [query]
    mode = strategy.rewrite_mode or "multi_query"
    note = ""
    if not strategy.use_rewrite:
        note = "策略未启用改写"
    elif round_no > 1 and hint:
        queries.append(f"{query}（{hint}）")
        note = f"第{round_no}轮带评估建议改写"
    elif mode == "multi_query":
        extra = await multi_query_expand(query)
        queries.extend(extra)
        note = f"多查询扩展 +{len(extra)}"
    elif mode == "hyde":
        doc = await hyde_document(query)
        if doc:
            queries.append(doc)
            note = "HyDE 假设文档检索"
    elif mode == "coref":
        if history:
            q2 = await coref_resolve(query, history)
            if q2 and q2 != query:
                queries = [q2, query]
                note = "指代消解改写"
        else:
            note = "无历史，跳过指代消解"
    trace = StageTrace(stage="rewrite", query=query, scale="none", threshold=None,
                       threshold_applies=False, note=note or f"改写模式 {mode}",
                       cost_ms=int((time.time() - t0) * 1000))
    traces.append(trace)
    return [q for q in queries if q]


async def retrieve_once(kb: KnowledgeBase, query: str, strategy: RetrievalStrategy,
                        history: list[dict] | None = None, round_no: int = 1,
                        hint: str = "", with_rewrite: bool = True) -> RetrievalOutput:
    """执行一轮完整混合检索，返回带全量 StageTrace 的结果。"""
    out = RetrievalOutput(rounds=round_no)
    queries = [query]
    if with_rewrite:
        queries = await _rewrite_stage(query, strategy, history, out.traces, round_no, hint)
    out.rewritten_queries = queries[1:]

    vec_map, vec_content = await _vector_stage(kb.id, queries, strategy, out.traces)
    bm25_map = await _bm25_stage(kb.id, queries, strategy, out.traces) if strategy.bm25_top_k > 0 else {}
    fused_map = _rrf_stage(vec_map, bm25_map, strategy, out.traces)
    if not fused_map:
        return out
    fused_order = list(fused_map.keys())
    parent_score, parent_content, parent_vec = await _backfill_stage(
        kb.id, fused_order, fused_map, vec_map, strategy, out.traces
    )
    if not parent_score:
        return out
    ordered = [pid for pid, _ in sorted(parent_score.items(), key=lambda x: x[1], reverse=True)]
    rerank_map = await _rerank_stage(query, ordered, parent_content, strategy, out.traces)

    rank = 0
    for pid in ordered:
        if pid not in rerank_map or rerank_map[pid] < 0:
            continue
        rank += 1
        scores = {"cosine": parent_vec.get(pid), "bm25": None, "rerank": rerank_map[pid]}
        ctx = RetrievedContext(chunk_id=pid, content=parent_content.get(pid, ""), scores=scores, rank=rank)
        out.contexts.append(ctx)
    return out


async def evaluate_context_sufficient(query: str, contexts: list[RetrievedContext]) -> tuple[bool, str, str]:
    """Agent 评估节点：LLM 判断当前上下文是否足以回答。"""
    from rag.llm import get_chat_model, get_prompt, render_prompt

    try:
        model = await get_chat_model(temperature=0)
        tpl, _ = await get_prompt("agent_evaluate_context")
        ctx_text = "\n\n".join(
            f"[{c.rank}] (余弦{c.scores.get('cosine')}) {c.content[:300]}" for c in contexts[:8]
        ) or "（无命中）"
        resp = await model.ainvoke(render_prompt(tpl, query=query, context=ctx_text))
        from rag.rewrite import parse_json_loose

        data = parse_json_loose(resp.content)
        return bool(data.get("sufficient")), str(data.get("reason", "")), str(data.get("rewrite_hint", ""))
    except Exception as e:
        # 评估失败时默认足够，直接生成（不让评估阻塞问答）
        return True, f"评估失败默认继续: {e}", ""


async def hybrid_retrieve(kb_id: int, query: str, strategy_id: int | None = None,
                          history: list[dict] | None = None) -> RetrievalOutput:
    """对外主入口：Agentic 循环由 graph.py 编排；此处提供单轮与自动多轮的统一入口。"""
    kb = await KnowledgeBase.filter(id=kb_id).first()
    if not kb:
        from common.exceptions import BizException

        raise BizException("知识库不存在")
    strategy = None
    if strategy_id:
        strategy = await RetrievalStrategy.filter(id=strategy_id).first()
    if not strategy:
        strategy = await RetrievalStrategy.filter(id=kb.retrieval_strategy_id).first()
    if not strategy:
        strategy = await RetrievalStrategy.first()
    if not strategy:
        from common.exceptions import BizException

        raise BizException("尚未配置任何检索策略，请先到 管理端→检索策略 新增一套")

    out = RetrievalOutput()
    hint, round_no = "", 1
    contexts: list[RetrievedContext] = []
    while round_no <= max(strategy.max_retrieval or 1, 1):
        res = await retrieve_once(kb, query, strategy, history, round_no, hint, with_rewrite=True)
        out.traces.extend(res.traces)
        contexts = res.contexts
        ok, reason, h = await evaluate_context_sufficient(query, contexts)
        if ok or round_no >= (strategy.max_retrieval or 1):
            break
        hint = h or reason
        round_no += 1
    out.contexts = contexts
    out.rounds = round_no
    return out
