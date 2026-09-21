"""效果评测：评测集 / 批量测评（LLM-as-judge 四指标）/ 策略对比看板（最多4套）"""
import asyncio
import json
import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import (
    ChatApp,
    CompareArm,
    CompareRun,
    EvalCase,
    EvalDataset,
    EvalRun,
    EvalRunItem,
    KnowledgeBase,
    RetrievalStrategy,
    User,
)
from rag.judge import judge_case
from rag.retriever import retrieve_once
from rag.qa import generate_once

router = APIRouter(tags=["效果评测"])


def _virtual_app() -> ChatApp:
    """评测生成用虚拟应用：默认模板 + 默认启用对话模型，不落库"""
    return ChatApp(id=0, name="__eval__", max_history=0, show_ref=1, use_agent=0, enabled=1)


# ---------------- 评测集 ----------------

class DatasetIn(BaseModel):
    name: str
    description: str = ""
    kb_id: int | None = None


@router.get("/eval/dataset/page")
async def dataset_page(query: str = Query(""), page: int = 1, page_size: int = 20, _: User = Depends(get_current_user)):
    qs = EvalDataset.all()
    if query:
        qs = qs.filter(name__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    for it in items:
        it["case_count"] = await EvalCase.filter(dataset_id=it["id"]).count()
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.get("/eval/dataset/options")
async def dataset_options(_: User = Depends(get_current_user)):
    return ok(await EvalDataset.all().order_by("-id").values("id", "name"))


@router.post("/eval/dataset")
async def dataset_create(body: DatasetIn, user: User = Depends(get_current_user)):
    ds = await EvalDataset.create(owner_id=user.id, **body.model_dump())
    return ok({"id": ds.id})


@router.put("/eval/dataset/{did}")
async def dataset_update(did: int, body: DatasetIn, _: User = Depends(get_current_user)):
    ds = await EvalDataset.filter(id=did).first()
    if not ds:
        raise BizException("评测集不存在")
    await ds.update_from_dict(body.model_dump()).save()
    return ok()


@router.delete("/eval/dataset/{did}")
async def dataset_delete(did: int, _: User = Depends(get_current_user)):
    await EvalCase.filter(dataset_id=did).delete()
    ds = await EvalDataset.filter(id=did).first()
    if ds:
        await ds.delete()
    return ok()


class CaseIn(BaseModel):
    question: str
    ground_truth: str = ""
    source_chunk_ids: list[int] = []


@router.get("/eval/case/page")
async def case_page(dataset_id: int, page: int = 1, page_size: int = 20, _: User = Depends(get_current_user)):
    qs = EvalCase.filter(dataset_id=dataset_id)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total = await qs.count()
    rows = await qs.offset(off).limit(ps).order_by("id").values()
    for r in rows:
        try:
            r["source_chunk_ids"] = json.loads(r.pop("source_chunk_ids_json") or "[]")
        except Exception:
            r["source_chunk_ids"] = []
    return ok({"list": rows, "total": total, "page": p, "page_size": ps})


@router.post("/eval/case")
async def case_create(dataset_id: int = Query(...), body: CaseIn = None, _: User = Depends(get_current_user)):
    if not body or not body.question.strip():
        raise BizException("问题不能为空")
    c = await EvalCase.create(
        dataset_id=dataset_id, question=body.question, ground_truth=body.ground_truth,
        source_chunk_ids_json=json.dumps(body.source_chunk_ids),
    )
    return ok({"id": c.id})


@router.post("/eval/case/batch")
async def case_batch(dataset_id: int = Query(...), body: dict = None, _: User = Depends(get_current_user)):
    """批量导入：[{question, ground_truth, source_chunk_ids}]"""
    items = (body or {}).get("cases") or []
    if not items:
        raise BizException("没有可导入的用例")
    rows = []
    for it in items:
        q = str(it.get("question", "")).strip()
        if not q:
            continue
        rows.append(EvalCase(
            dataset_id=dataset_id, question=q, ground_truth=str(it.get("ground_truth", "")),
            source_chunk_ids_json=json.dumps(it.get("source_chunk_ids") or []),
        ))
    if rows:
        await EvalCase.bulk_create(rows)
    return ok({"created": len(rows)})


@router.delete("/eval/case/{cid}")
async def case_delete(cid: int, _: User = Depends(get_current_user)):
    c = await EvalCase.filter(id=cid).first()
    if c:
        await c.delete()
    return ok()


# ---------------- 批量测评 ----------------

class RunIn(BaseModel):
    dataset_id: int
    kb_id: int
    strategy_id: int | None = None
    report_name: str = "评测报告"


async def _eval_run_task(run_id: int):
    run = await EvalRun.filter(id=run_id).first()
    if not run:
        return
    run.status = "running"
    await run.save()
    t0 = time.time()
    try:
        cases = await EvalCase.filter(dataset_id=run.dataset_id).all()
        if not cases:
            raise RuntimeError("评测集没有用例")
        kb = await KnowledgeBase.filter(id=run.kb_id).first()
        if not kb:
            raise RuntimeError("知识库不存在")
        strategy = None
        if run.strategy_id:
            strategy = await RetrievalStrategy.filter(id=run.strategy_id).first()
        if not strategy:
            strategy = await RetrievalStrategy.filter(id=kb.retrieval_strategy_id).first() or await RetrievalStrategy.first()
        app = _virtual_app()
        metrics = {"recall": 0.0, "precision": 0.0, "faithfulness": 0.0, "relevancy": 0.0, "overall": 0.0}
        for case in cases:
            try:
                expected_ids = []
                try:
                    expected_ids = json.loads(case.source_chunk_ids_json or "[]")
                except Exception:
                    pass
                out = await retrieve_once(kb, case.question, strategy, with_rewrite=False)
                contexts = [{"chunk_id": c.chunk_id, "content": c.content, "scores": c.scores}
                            for c in out.contexts]
                retrieved_ids = [c.chunk_id for c in out.contexts]
                answer, _cost = await generate_once(app, case.question, out.contexts, [])
                m = await judge_case(case.question, answer, contexts, expected_ids, retrieved_ids)
                await EvalRunItem.create(
                    run_id=run.id, case_id=case.id, question=case.question,
                    contexts_json=json.dumps(contexts, ensure_ascii=False)[:60000],
                    context_ids_json=json.dumps(retrieved_ids),
                    answer=answer, detail_json=json.dumps(m),
                    recall=m["recall"], precision=m["precision"],
                    faithfulness=m["faithfulness"], relevancy=m["relevancy"], overall=m["overall"],
                )
                for k in metrics:
                    metrics[k] += m[k]
            except Exception as e:
                await EvalRunItem.create(
                    run_id=run.id, case_id=case.id, question=case.question,
                    answer="", detail_json=json.dumps({"error": str(e)}),
                )
        n = max(len(cases), 1)
        for k in metrics:
            metrics[k] = round(metrics[k] / n, 4)
        run.status = "done"
        run.case_count = len(cases)
        run.recall, run.precision = metrics["recall"], metrics["precision"]
        run.faithfulness, run.relevancy = metrics["faithfulness"], metrics["relevancy"]
        run.overall = metrics["overall"]
        await run.save()
    except Exception as e:
        run.status = "failed"
        run.error = f"{type(e).__name__}: {e}"
        await run.save()


@router.post("/eval/run")
async def run_create(body: RunIn, _: User = Depends(get_current_user)):
    if not await EvalCase.filter(dataset_id=body.dataset_id).exists():
        raise BizException("评测集没有用例，先导入用例")
    run = await EvalRun.create(
        dataset_id=body.dataset_id, kb_id=body.kb_id, strategy_id=body.strategy_id,
        report_name=body.report_name or "评测报告", status="pending",
        case_count=await EvalCase.filter(dataset_id=body.dataset_id).count(),
    )
    asyncio.get_event_loop().create_task(_eval_run_task(run.id))
    return ok({"id": run.id, "msg": "评测在后台执行，完成后刷新列表即可看到分数"})


@router.get("/eval/run/page")
async def run_page(page: int = 1, page_size: int = 10, _: User = Depends(get_current_user)):
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(EvalRun.all(), p, ps, off)
    for it in items:
        kb = await KnowledgeBase.filter(id=it["kb_id"]).first()
        it["kb_name"] = kb.name if kb else ""
        ds = await EvalDataset.filter(id=it["dataset_id"]).first()
        it["dataset_name"] = ds.name if ds else ""
        st = await RetrievalStrategy.filter(id=it["strategy_id"]).first() if it.get("strategy_id") else None
        it["strategy_name"] = st.name if st else "库默认策略"
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.get("/eval/run/{run_id}/items")
async def run_items(run_id: int, _: User = Depends(get_current_user)):
    rows = await EvalRunItem.filter(run_id=run_id).order_by("id").values()
    return ok(rows)


@router.delete("/eval/run/{run_id}")
async def run_delete(run_id: int, _: User = Depends(get_current_user)):
    await EvalRunItem.filter(run_id=run_id).delete()
    r = await EvalRun.filter(id=run_id).first()
    if r:
        await r.delete()
    return ok()


# ---------------- 策略对比看板 ----------------

class CompareIn(BaseModel):
    name: str = "策略对比"
    kb_id: int
    dataset_id: int
    strategy_ids: list[int]


async def _compare_task(run_id: int):
    run = await CompareRun.filter(id=run_id).first()
    if not run:
        return
    run.status = "running"
    await run.save()
    try:
        cases = await EvalCase.filter(dataset_id=run.dataset_id).all()
        arms = await CompareArm.filter(run_id=run.id).order_by("arm_index").all()
        kb = await KnowledgeBase.filter(id=run.kb_id).first()
        app = _virtual_app()
        for arm in arms:
            strategy = await RetrievalStrategy.filter(id=arm.strategy_id).first()
            if not strategy or not cases:
                continue
            metrics = {"recall": 0.0, "precision": 0.0, "faithfulness": 0.0, "relevancy": 0.0, "overall": 0.0}
            cost_total = 0
            for case in cases:
                try:
                    expected_ids = json.loads(case.source_chunk_ids_json or "[]")
                except Exception:
                    expected_ids = []
                t0 = time.time()
                out = await retrieve_once(kb, case.question, strategy, with_rewrite=False)
                cost_total += int((time.time() - t0) * 1000)
                contexts = [{"chunk_id": c.chunk_id, "content": c.content, "scores": c.scores}
                            for c in out.contexts]
                retrieved_ids = [c.chunk_id for c in out.contexts]
                answer, _cost = await generate_once(app, case.question, out.contexts, [])
                m = await judge_case(case.question, answer, contexts, expected_ids, retrieved_ids)
                for k in metrics:
                    metrics[k] += m[k]
            n = max(len(cases), 1)
            for k in metrics:
                metrics[k] = round(metrics[k] / n, 4)
            arm.recall, arm.precision = metrics["recall"], metrics["precision"]
            arm.faithfulness, arm.relevancy = metrics["faithfulness"], metrics["relevancy"]
            arm.overall = metrics["overall"]
            arm.avg_cost_ms = cost_total // n
            await arm.save()
        run.status = "done"
        await run.save()
    except Exception as e:
        run.status = "failed"
        run.error = f"{type(e).__name__}: {e}"
        await run.save()


@router.post("/eval/compare")
async def compare_create(body: CompareIn, _: User = Depends(get_current_user)):
    if not (2 <= len(body.strategy_ids) <= 4):
        raise BizException("策略对比需要 2~4 套检索策略")
    run = await CompareRun.create(name=body.name, kb_id=body.kb_id, dataset_id=body.dataset_id,
                                  status="pending", arm_count=len(body.strategy_ids))
    for i, sid in enumerate(body.strategy_ids):
        st = await RetrievalStrategy.filter(id=sid).first()
        await CompareArm.create(run_id=run.id, arm_index=i, strategy_id=sid,
                                strategy_name=st.name if st else f"策略{sid}")
    asyncio.get_event_loop().create_task(_compare_task(run.id))
    return ok({"id": run.id, "msg": "对比任务已启动"})


@router.get("/eval/compare/page")
async def compare_page(page: int = 1, page_size: int = 10, _: User = Depends(get_current_user)):
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(CompareRun.all(), p, ps, off)
    for it in items:
        ds = await EvalDataset.filter(id=it["dataset_id"]).first()
        it["dataset_name"] = ds.name if ds else ""
        kb = await KnowledgeBase.filter(id=it["kb_id"]).first()
        it["kb_name"] = kb.name if kb else ""
        it["arms"] = await CompareArm.filter(run_id=it["id"]).order_by("arm_index").values(
            "arm_index", "strategy_name", "recall", "precision", "faithfulness", "relevancy", "overall", "avg_cost_ms")
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.delete("/eval/compare/{run_id}")
async def compare_delete(run_id: int, _: User = Depends(get_current_user)):
    await CompareArm.filter(run_id=run_id).delete()
    r = await CompareRun.filter(id=run_id).first()
    if r:
        await r.delete()
    return ok()
