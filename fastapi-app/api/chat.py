"""SSE 流式问答与会话（asyncio.Queue 桥接内部回调 → SSE 事件流）"""
import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from models import AgentRun, ChatApp, ChatMessage, ChatSession, User
from rag.graph import run_agent
from rag.qa import app_retrieve, stream_generate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["对话"])


class AskIn(BaseModel):
    session_id: int
    query: str


class FeedbackIn(BaseModel):
    message_id: int
    feedback: str  # useful / useless / 空=取消


async def _get_session(session_id: int, user: User) -> ChatSession:
    s = await ChatSession.filter(id=session_id, user_id=user.id).first()
    if not s:
        raise BizException("会话不存在")
    return s


async def _history(session_id: int, limit: int = 3, exclude_last_user: bool = False) -> list[dict]:
    """取最近 limit 轮对话历史（一轮=用户+助手两条）。"""
    limit = max(int(limit or 0), 0)
    if limit == 0:
        return []
    rows = await ChatMessage.filter(session_id=session_id).order_by("-id").limit(limit * 2).all()
    rows.reverse()
    hist = [{"role": m.role, "content": m.content} for m in rows]
    if exclude_last_user and hist and hist[-1].get("role") == "user":
        hist = hist[:-1]
    return hist[-(limit * 2):]


@router.get("/chat/session/page")
async def session_page(app_id: int = 0, page: int = 1, page_size: int = 50, user: User = Depends(get_current_user)):
    qs = ChatSession.filter(user_id=user.id)
    if app_id:
        qs = qs.filter(app_id=app_id)
    total = await qs.count()
    rows = await qs.offset((page - 1) * page_size).limit(page_size).order_by("-updated_at").values()
    return ok({"list": rows, "total": total})


@router.post("/chat/session")
async def create_session(body: dict, user: User = Depends(get_current_user)):
    app_id = int(body.get("app_id") or 0)
    app = await ChatApp.filter(id=app_id, enabled=1).first()
    if not app:
        raise BizException("应用不存在或未启用")
    s = await ChatSession.create(app_id=app.id, user_id=user.id, title=str(body.get("title") or "新会话")[:50])
    return ok({"id": s.id, "title": s.title})


@router.delete("/chat/session/{sid}")
async def delete_session(sid: int, user: User = Depends(get_current_user)):
    s = await _get_session(sid, user)
    await ChatMessage.filter(session_id=s.id).delete()
    await s.delete()
    return ok()


@router.get("/chat/history/{sid}")
async def history(sid: int, user: User = Depends(get_current_user)):
    s = await _get_session(sid, user)
    rows = await ChatMessage.filter(session_id=s.id).order_by("id").values()
    return ok(rows)


@router.post("/chat/feedback")
async def feedback(body: FeedbackIn, user: User = Depends(get_current_user)):
    """答案 点赞/点踩（踩的问题计入首页「待回答优化」）"""
    m = await ChatMessage.filter(id=body.message_id, user_id=user.id).first()
    if not m:
        raise BizException("消息不存在")
    m.feedback = body.feedback if body.feedback in ("useful", "useless", "") else ""
    await m.save()
    return ok()


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False, default=str)}\n\n"


@router.post("/chat/ask")
async def ask(body: AskIn, user: User = Depends(get_current_user)):
    """SSE 流式问答。事件：start / agent_start / step / token / refs / done / error"""
    session = await _get_session(body.session_id, user)
    app = await ChatApp.filter(id=session.app_id, enabled=1).first()
    if not app:
        raise BizException("应用不存在或未启用")
    query = body.query.strip()
    if not query:
        raise BizException("问题不能为空")

    async def gen():
        queue: asyncio.Queue = asyncio.Queue()

        async def producer():
            t0 = time.time()
            agent_run = None
            try:
                await queue.put({"type": "start", "session_id": session.id, "app": app.name,
                                 "use_agent": bool(app.use_agent)})
                await ChatMessage.create(session_id=session.id, app_id=app.id, user_id=user.id,
                                         role="user", content=query)
                history = await _history(session.id, app.max_history or 3, exclude_last_user=True)

                async def on_token(delta: str):
                    await queue.put({"type": "token", "delta": delta})

                agent_run_id = None
                if app.use_agent:
                    agent_run = await AgentRun.create(app_id=app.id, session_id=session.id,
                                                      user_id=user.id, query=query, status="running")
                    agent_run_id = agent_run.id
                    await queue.put({"type": "agent_start", "run_id": agent_run.id})

                    async def emit(payload: dict):
                        await queue.put({"type": "step", "data": payload})

                    result = await run_agent(app.id, query, history=history,
                                             agent_run_id=agent_run.id, emit=emit,
                                             on_token=on_token)
                    answer = result["answer"]
                    refs = result["contexts"]
                    agent_run.status = "done"
                    agent_run.rounds = result["rounds"]
                    agent_run.final_answer = answer
                    agent_run.total_cost_ms = result["cost_ms"]
                    await agent_run.save()
                else:
                    contexts, traces, _rounds = await app_retrieve(app, query, history)
                    for t in traces:
                        await queue.put({"type": "trace", "data": t.to_dict()})
                    answer, _cost = await stream_generate(app, query, contexts, history, on_token=on_token)
                    refs = [{"rank": c.rank, "chunk_id": c.chunk_id, "scores": c.scores,
                             "content": c.content} for c in contexts]

                show = []
                if app.show_ref:
                    for r in refs:
                        show.append({"rank": r.get("rank"), "chunk_id": r.get("chunk_id"),
                                     "scores": r.get("scores", {}),
                                     "content": (r.get("content") or "")[:300]})
                await queue.put({"type": "refs", "refs": show})

                cost_ms = int((time.time() - t0) * 1000)
                msg = await ChatMessage.create(
                    session_id=session.id, app_id=app.id, user_id=user.id, role="assistant",
                    content=answer, refs_json=json.dumps(refs, ensure_ascii=False, default=str)[:30000],
                    cost_ms=cost_ms, agent_run_id=agent_run_id,
                )
                session.msg_count = await ChatMessage.filter(session_id=session.id).count()
                if session.title in ("新会话", ""):
                    session.title = query[:20]
                await session.save()
                await queue.put({"type": "done", "message_id": msg.id, "cost_ms": cost_ms,
                                 "agent_run_id": agent_run_id})
            except BizException as e:
                if agent_run is not None:
                    agent_run.status = "failed"
                    agent_run.final_answer = e.msg
                    await agent_run.save()
                await queue.put({"type": "error", "message": e.msg})
            except Exception as e:
                logger.exception("SSE 问答执行失败 session=%s app=%s", session.id, app.id)
                msg = f"{type(e).__name__}: {e}".strip().rstrip(":") or repr(e)
                if agent_run is not None:
                    agent_run.status = "failed"
                    agent_run.final_answer = msg[:2000]
                    await agent_run.save()
                await queue.put({"type": "error", "message": msg})
            finally:
                await queue.put(None)

        task = asyncio.create_task(producer())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield sse(item)
        await task

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
