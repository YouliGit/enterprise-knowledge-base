"""Agent 执行与运行记录（时间线回放）"""
import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import AgentRun, AgentStep, ChatApp, User
from rag.graph import run_agent

router = APIRouter(tags=["Agent"])


class RunIn(BaseModel):
    app_id: int
    query: str


@router.post("/agent/run")
async def run(body: RunIn, user: User = Depends(get_current_user)):
    """同步执行一次 Agentic RAG（管理端调试用；用户端问答走 /chat/ask SSE）"""
    app = await ChatApp.filter(id=body.app_id).first()
    if not app:
        raise BizException("应用不存在")
    run_row = await AgentRun.create(app_id=app.id, user_id=user.id, query=body.query, status="running")
    try:
        result = await run_agent(app.id, body.query, agent_run_id=run_row.id)
        run_row.status = "done"
        run_row.rounds = result["rounds"]
        run_row.final_answer = result["answer"]
        run_row.total_cost_ms = result["cost_ms"]
        await run_row.save()
        return ok({"run_id": run_row.id, **result})
    except Exception as e:
        run_row.status = "failed"
        run_row.final_answer = str(e)[:2000]
        await run_row.save()
        raise BizException(f"Agent执行失败: {e}")


@router.get("/agent/runPage")
async def run_page(query: str = Query(""), page: int = 1, page_size: int = 10, _: User = Depends(get_current_user)):
    qs = AgentRun.all()
    if query:
        qs = qs.filter(query__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.get("/agent/run/{run_id}")
async def run_detail(run_id: int, _: User = Depends(get_current_user)):
    row = await AgentRun.filter(id=run_id).first()
    if not row:
        raise BizException("记录不存在")
    return ok({"run": {k: str(getattr(row, k)) if not isinstance(getattr(row, k), (int, str)) else getattr(row, k)
                       for k in ("id", "app_id", "query", "status", "rounds", "final_answer", "total_cost_ms")}})


@router.get("/agent/steps/{run_id}")
async def steps(run_id: int, _: User = Depends(get_current_user)):
    rows = await AgentStep.filter(run_id=run_id).order_by("seq").values()
    return ok(rows)
