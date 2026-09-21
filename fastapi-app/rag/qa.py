"""问答生成：按应用绑定模板渲染上下文并流式输出（含 Function Calling 工具循环）。"""
import logging
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from common.exceptions import BizException
from models import ChatApp, RetrievalStrategy
from rag.llm import get_chat_model, get_prompt, render_prompt
from rag.retriever import RetrievedContext, evaluate_context_sufficient, retrieve_once

logger = logging.getLogger(__name__)


def build_context_block(contexts: list[RetrievedContext]) -> str:
    """把父块上下文编号成 [1][2] 供模板引用与答案标注出处。"""
    return "\n\n".join(f"[{i}] {c.content}" for i, c in enumerate(contexts, start=1))


async def _build_messages(app: ChatApp, query: str, context: str, history: list[dict]):
    tpl_id = app.prompt_template_id
    tpl_content, _ = None, None
    if tpl_id:
        from models import PromptTemplate

        tpl = await PromptTemplate.filter(id=tpl_id, enabled=1).first()
        tpl_content = tpl.content if tpl else None
    if not tpl_content:
        tpl_content, _ = await get_prompt("qa_answer_with_source")
    system = render_prompt(tpl_content, query=query, context=context)
    msgs = [SystemMessage(content=system)]
    for m in (history or [])[-(app.max_history or 3) * 2:]:
        if m.get("role") == "user":
            msgs.append(HumanMessage(content=str(m.get("content", ""))[:2000]))
        else:
            msgs.append(AIMessage(content=str(m.get("content", ""))[:2000]))
    msgs.append(HumanMessage(content=query))
    return msgs


async def stream_generate(app: ChatApp, query: str, contexts: list[RetrievedContext],
                          history: list[dict], on_token, on_tool=None):
    """生成答案：逐 token 流式推送。

    - 无工具：直接 astream 真·流式。
    - 有工具：前几轮用「非流式 ainvoke」只为拿到 tool_calls（流式协议下拿工具参数很脆弱），
      一旦模型不再要工具（即最终作答轮），改用 astream 逐 token 推送——
      保证「流式问答」在前端仍是逐字效果，而不是等全部生成完再一次性吐出来。

    :param on_token: async fn(delta_text) —— SSE 逐字推送
    :param on_tool:  async fn(tool_code, args, result) —— 工具调用事件
    """
    from rag.tools import get_enabled_tools, execute_tool

    t0 = time.time()
    context_block = build_context_block(contexts)
    messages = await _build_messages(app, query, context_block, history)
    tools = await get_enabled_tools()

    async def _stream_final(model) -> str:
        """最终作答轮：逐 token 流式，返回完整文本。"""
        parts: list[str] = []
        async for chunk in model.astream(messages):
            delta = chunk.content
            if isinstance(delta, list):
                delta = "".join(str(x) for x in delta)
            if delta:
                parts.append(delta)
                try:
                    await on_token(delta)
                except Exception:
                    pass
        text = "".join(parts)
        if not text:
            # 模型确实没吐内容时，保证 SSE 与落库都拿到占位串，避免前端空白
            text = "（模型未返回内容）"
            try:
                await on_token(text)
            except Exception:
                pass
        return text

    if not tools:
        model = await get_chat_model(purpose="stream", cfg_id=app.model_config_id)
        return await _stream_final(model), int((time.time() - t0) * 1000)

    model = await get_chat_model(purpose="chat", cfg_id=app.model_config_id)
    bound = model.bind_tools(tools)
    full = ""
    for _round in range(3):  # 工具循环上限2轮工具+1轮最终作答
        resp = await bound.ainvoke(messages)
        tool_calls = list(getattr(resp, "tool_calls", None) or [])
        if not tool_calls:
            # 不再需要工具 → 进入最终作答：流式重放一次，保证逐字输出
            full = await _stream_final(model)
            break
        messages.append(resp)
        for tc in tool_calls:
            args = tc.get("args") or {}
            result = await execute_tool(tc.get("name", ""), args, on_tool=on_tool)
            from langchain_core.messages import ToolMessage

            messages.append(ToolMessage(content=str(result)[:4000], tool_call_id=tc.get("id", "")))
    else:
        # 工具轮次用尽仍未收敛：用「模型直答」兜底，不能静默返回空答案
        logger.warning("工具循环达到上限仍未收敛，改用直答兜底 query=%r", query)
        full = await _stream_final(model)
    return full, int((time.time() - t0) * 1000)


async def generate_once(app: ChatApp, query: str, contexts: list[RetrievedContext], history: list[dict],
                        on_tool=None, on_token=None) -> tuple[str, int]:
    """非流式/回调式生成（Agent 图 / 评测 / 对比用）"""
    chunks: list[str] = []

    async def collect(_t: str):
        chunks.append(_t)
        if on_token:
            try:
                await on_token(_t)
            except Exception:
                pass

    text, cost = await stream_generate(app, query, contexts, history, on_token=collect, on_tool=on_tool)
    return text, cost


async def app_retrieve(app: ChatApp, query: str, history: list[dict]):
    """应用检索入口：走应用绑定的策略与知识库集合（多库合并检索）。"""
    from models import AppKbRel
    from rag.retriever import retrieve_once, evaluate_context_sufficient

    rels = await AppKbRel.filter(app_id=app.id).values("kb_id")
    kb_ids = [r["kb_id"] for r in rels]
    if not kb_ids:
        raise BizException("该应用未绑定知识库，请到 管理端→问答应用→应用管理 配置")
    strategy = None
    if app.retrieval_strategy_id:
        strategy = await RetrievalStrategy.filter(id=app.retrieval_strategy_id).first()
    if not strategy:
        from models import KnowledgeBase
        kb0 = await KnowledgeBase.filter(id=kb_ids[0]).first()
        if kb0 and kb0.retrieval_strategy_id:
            strategy = await RetrievalStrategy.filter(id=kb0.retrieval_strategy_id).first()
    if not strategy:
        strategy = await RetrievalStrategy.first()
    if not strategy:
        raise BizException("尚未配置任何检索策略，请先到 管理端→检索策略 新增一套")

    from models import KnowledgeBase

    all_ctx: list[RetrievedContext] = []
    traces = []
    hint, round_no = "", 1
    max_rounds = max(strategy.max_retrieval or 1, 1)
    while round_no <= max_rounds:
        all_ctx, traces = [], []
        for kb_id in kb_ids:
            kb = await KnowledgeBase.filter(id=kb_id, status=1).first()
            if not kb:
                continue
            res = await retrieve_once(kb, query, strategy, history, round_no, hint)
            all_ctx.extend(res.contexts)
            for t in res.traces:
                t.note = f"[{kb.name}] {t.note}" if t.note else f"[{kb.name}]"
            traces.extend(res.traces)
        all_ctx.sort(key=lambda c: (c.scores.get("rerank", -1) if c.scores.get("rerank") is not None else -1), reverse=True)
        all_ctx = all_ctx[: strategy.rerank_top_n or 5]
        for i, c in enumerate(all_ctx, start=1):
            c.rank = i
        ok, reason, h = await evaluate_context_sufficient(query, all_ctx)
        if ok or round_no >= max_rounds:
            break
        hint = h or reason
        round_no += 1
    return all_ctx, traces, round_no
