"""LangGraph Agentic RAG 状态图：检索 → 评估 → 改写 → 再检索 → 生成 → 自查。

检索几轮、改写几次、答案不合格要不要重来，全由模型每一轮判断决定，
代码只设循环上限（策略表 max_retrieval / 自查重试上限 1 次）。
每一步落 agent_step，配合 agent_run 与前端时间线完整回放。
"""
import json
import time
from typing import Any, Callable, Optional, TypedDict

from langgraph.graph import END, StateGraph

from models import AgentRun, AgentStep
from rag.qa import app_retrieve, generate_once
from rag.retriever import evaluate_context_sufficient
from rag.rewrite import coref_resolve

NODE_NAME_CN = {
    "retrieve": "检索",
    "evaluate": "评估",
    "rewrite": "改写",
    "generate": "生成",
    "self_check": "自查",
    "tool": "工具调用",
}

SELF_CHECK_RETRY_LIMIT = 1

# 图级检索轮次硬上限：改写→再检索最多走这么多轮，防止评估节点持续判"不足"时无限循环
AGENT_MAX_ROUNDS = 3

# LangGraph 递归上限兜底：图里每个节点算一步，轮次上限 × 每轮节点数(3) + 生成/自查余量
# 留足冗余，避免"改写→检索→评估"多走几圈就撞上限报 GraphRecursionError
AGENT_RECURSION_LIMIT = 50


class AgentState(TypedDict, total=False):
    app_id: int
    query: str
    history: list
    round: int
    hint: str
    contexts: list          # list[RetrievedContext]
    traces: list            # list[StageTrace dict]
    answer: str
    check: dict
    check_retries: int
    self_check_retry: bool
    agent_run_id: int
    seq: int
    rounds_used: int
    emit: Optional[Callable]  # SSE 步骤事件回调（内存态，不落库）
    on_token: Optional[Callable]  # SSE token 流式回调


async def _next_seq(state: dict) -> int:
    """取本 run 的下一个步骤序号。

    LangGraph 每个节点拿到的是 state 的副本，节点内对 state["seq"] 的改动不会回流到
    图级 state，所以不能靠内存计数（否则每个节点都从 0 开始，全落成 seq=1）。
    这里以库中已有的最大 seq 为准，天然保证唯一且递增。
    """
    run_id = state.get("agent_run_id")
    if run_id:
        last = await AgentStep.filter(run_id=run_id).order_by("-seq").first()
        return int(last.seq) + 1 if last else 1
    return int(state.get("seq", 0)) + 1


async def _emit_step(state: dict, node: str, action: str, thought: str,
                     step_input: Any, output: Any, cost_ms: int, status: str = "ok"):
    """落 agent_step + 可选实时回调前端"""
    seq = await _next_seq(state)
    state["seq"] = seq
    payload = {
        "seq": seq,
        "node": node,
        "node_cn": NODE_NAME_CN.get(node, node),
        "action": action,
        "thought": thought,
        "cost_ms": cost_ms,
        "status": status,
    }
    run_id = state.get("agent_run_id")
    if run_id:
        await AgentStep.create(
            run_id=run_id,
            seq=seq,
            node=node,
            action=action,
            thought=thought or "",
            input_json=json.dumps(step_input if not isinstance(step_input, str) else {"text": step_input}, ensure_ascii=False, default=str)[:6000],
            output_json=json.dumps(output if not isinstance(output, str) else {"text": output}, ensure_ascii=False, default=str)[:6000],
            status=status,
            cost_ms=cost_ms,
        )
    emit = state.get("emit")
    if emit:
        try:
            await emit(payload)
        except Exception:
            pass
    return seq


async def node_retrieve(state: dict) -> dict:
    """检索节点：一轮混合检索（含阶段追踪）"""
    from models import ChatApp

    t0 = time.time()
    app = await ChatApp.filter(id=state["app_id"]).first()
    contexts, traces, _inner_rounds = await app_retrieve(app, state["query"], state.get("history") or [])
    previews = [
        {"rank": c.rank, "chunk_id": c.chunk_id, "scores": c.scores, "preview": c.content[:80]}
        for c in contexts
    ]
    await _emit_step(
        state, "retrieve", f"第{state.get('round', 1)}轮混合检索",
        f"命中{len(contexts)}个父块",
        {"query": state["query"]}, {"contexts": previews, "traces": traces},
        int((time.time() - t0) * 1000),
    )
    return {"contexts": contexts, "traces": state.get("traces", []) + traces, "rounds_used": state.get("round", 1)}


async def node_evaluate(state: dict) -> dict:
    """评估节点：模型判断资料是否足够（决定要不要改写重检）"""
    t0 = time.time()
    ok, reason, hint = await evaluate_context_sufficient(state["query"], state.get("contexts") or [])
    await _emit_step(
        state, "evaluate", "评估召回质量", reason or ("资料充分" if ok else "资料不足"),
        {"context_count": len(state.get("contexts") or [])},
        {"sufficient": ok, "rewrite_hint": hint},
        int((time.time() - t0) * 1000),
    )
    return {"check": {"sufficient": ok, "reason": reason, "hint": hint}}


def route_after_evaluate(state: dict) -> str:
    """模型判断 + 循环上限共同决定：资料不足且未超检索轮次上限 → 改写再检索。

    注意：这里必须以图级轮次 state["round"] 为准。node_retrieve 返回的 rounds_used
    是 app_retrieve 内部的轮次（恒为 1~max_retrieval），拿它当循环条件会导致
    "改写→检索→评估→改写" 永不收敛，直到 LangGraph 递归上限报 GraphRecursionError。
    """
    if state.get("check", {}).get("sufficient"):
        return "generate"
    round_no = int(state.get("round", 1) or 1)
    return "rewrite" if round_no < AGENT_MAX_ROUNDS else "generate"


async def node_rewrite(state: dict) -> dict:
    """改写节点：带评估建议重写查询（指代消解 + 建议融合）"""
    t0 = time.time()
    new_query = await coref_resolve(state["query"], state.get("history") or [])
    hint = state.get("check", {}).get("hint", "")
    if hint:
        new_query = f"{new_query} {hint}".strip()
    await _emit_step(
        state, "rewrite", "改写查询后重检",
        state.get("check", {}).get("reason", ""),
        {"old": state["query"]}, {"new": new_query},
        int((time.time() - t0) * 1000),
    )
    return {"query": new_query, "round": int(state.get("round", 1)) + 1}


async def node_generate(state: dict) -> dict:
    """生成节点：模板渲染 + 工具调用循环（工具步骤由 tools.execute_tool 落日志）"""
    from models import ChatApp

    t0 = time.time()
    app = await ChatApp.filter(id=state["app_id"]).first()
    tool_events: list[dict] = []

    async def on_tool(code, args, result):
        item = {"tool": code, "args": args, "result": str(result)[:200]}
        tool_events.append(item)
        await _emit_step(state, "tool", f"调用工具 {code}", "", args, item, 0)

    strict = "（上一次答案未通过自查，请更严格地只依据参考资料作答）" if int(state.get("check_retries", 0)) > 0 else ""
    answer, cost_ms = await generate_once(app, state["query"], state.get("contexts") or [],
                                          state.get("history") or [], on_tool=on_tool,
                                          on_token=state.get("on_token"))
    await _emit_step(
        state, "generate", "生成答案", strict or f"基于{len(state.get('contexts') or [])}个片段作答",
        {"query": state["query"]}, {"answer": answer[:500], "tool_calls": tool_events},
        int((time.time() - t0) * 1000),
    )
    # 清除上一轮的自查重试标记，让随后的自查节点重新决策
    return {"answer": answer, "self_check_retry": False}


async def node_self_check(state: dict) -> dict:
    """自查节点：模型判断答案是否忠于资料、是否跑题；不合格且未超重试上限 → 重新生成"""
    from rag.llm import get_chat_model, get_prompt, render_prompt
    from rag.rewrite import parse_json_loose

    t0 = time.time()
    retries = int(state.get("check_retries", 0))
    verdict = {"pass": True, "reason": ""}
    try:
        from rag.qa import build_context_block

        model = await get_chat_model(temperature=0)
        tpl, _ = await get_prompt("agent_self_check")
        resp = await model.ainvoke(render_prompt(
            tpl,
            query=state["query"],
            context=build_context_block((state.get("contexts") or [])[:6])[:3000],
            answer=state.get("answer", "")[:2000],
        ))
        data = parse_json_loose(resp.content)
        verdict = {"pass": bool(data.get("pass", True)), "reason": str(data.get("reason", ""))}
    except Exception as e:
        verdict = {"pass": True, "reason": f"自查异常默认通过: {e}"}
    await _emit_step(
        state, "self_check", "答案质检", verdict.get("reason", ""),
        {"answer": state.get("answer", "")[:300]},
        {"pass": verdict["pass"], "retries": retries},
        int((time.time() - t0) * 1000),
        status="ok" if verdict["pass"] else "retry",
    )
    retry = (not verdict["pass"]) and retries < SELF_CHECK_RETRY_LIMIT
    if retry:
        # 只有本次真的"授权重试"才回生成节点；否则收敛到 END
        return {"check": {"sufficient": False, "hint": verdict["reason"]},
                "check_retries": retries + 1, "self_check_retry": True}
    return {"self_check_retry": False}


def route_after_self_check(state: dict) -> str:
    """仅在自查节点刚刚授权了一次重试时回生成节点，其余情况一律收敛。

    注意不能用 check_retries>0 判断：重试那轮自查仍可能不通过，
    此时 retries 已到上限、不再自增，但 check.sufficient 依旧是 False，
    按旧逻辑会永远回 generate，直到撞 LangGraph 递归上限。
    """
    return "generate" if state.get("self_check_retry") else END


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("retrieve", node_retrieve)
    builder.add_node("evaluate", node_evaluate)
    builder.add_node("rewrite", node_rewrite)
    builder.add_node("generate", node_generate)
    builder.add_node("self_check", node_self_check)

    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "evaluate")
    builder.add_conditional_edges("evaluate", route_after_evaluate, {"rewrite": "rewrite", "generate": "generate"})
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("generate", "self_check")
    builder.add_conditional_edges("self_check", route_after_self_check, {"generate": "generate", END: END})
    return builder.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


async def run_agent(app_id: int, query: str, history: list | None = None,
                    agent_run_id: int | None = None, emit=None, on_token=None) -> dict:
    """执行完整状态图，返回 {answer, contexts, traces, rounds, cost_ms}"""
    t0 = time.time()
    state: dict = {
        "app_id": app_id,
        "query": query,
        "history": history or [],
        "round": 1,
        "hint": "",
        "contexts": [],
        "traces": [],
        "answer": "",
        "check": {},
        "check_retries": 0,
        "agent_run_id": agent_run_id or 0,
        "seq": 0,
        "rounds_used": 1,
        "emit": emit,
        "on_token": on_token,
    }
    final = await get_graph().ainvoke(state, config={"recursion_limit": AGENT_RECURSION_LIMIT})
    answer = final.get("answer", "")
    contexts = [
        {"rank": c.rank, "chunk_id": c.chunk_id, "scores": c.scores, "content": c.content}
        for c in (final.get("contexts") or [])
    ]
    return {
        "answer": answer,
        "contexts": contexts,
        "traces": final.get("traces") or [],
        "rounds": int(final.get("rounds_used") or 1),
        "cost_ms": int((time.time() - t0) * 1000),
    }
