"""LLM-as-judge 四指标评测。

- Context Recall    该找的资料找回来没有   → 不靠模型：用例记录来源片段ID，直接集合运算（参照精确到单条，避免分母被撑大）
- Context Precision 有用的资料排在前面没有 → 裁判模型
- Faithfulness      答案有没有编          → 裁判模型
- Answer Relevancy  有没有跑题            → 裁判模型
裁判模型 temperature 固定为 0。
"""
import re

from rag.llm import get_judge_model, get_prompt, render_prompt
from rag.rewrite import parse_json_loose


def context_recall(expected_ids: list[int], retrieved_ids: list[int]) -> float:
    """集合运算：找回的期望片段 / 全部期望片段。期望列表为空时返回 0（无法判定）。"""
    expected = {int(x) for x in expected_ids or []}
    if not expected:
        return 0.0
    retrieved = {int(x) for x in retrieved_ids or []}
    return round(len(expected & retrieved) / len(expected), 4)


def _clip01(v: float) -> float:
    try:
        v = float(v)
    except Exception:
        return 0.0
    return round(max(0.0, min(1.0, v)), 4)


def _first_number(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text or "")
    return float(m.group(0)) if m else None


async def judge_context_precision(question: str, contexts: list[dict]) -> float:
    """裁判逐条判断片段是否有用，求平均（排名靠前的无用片段会拉低分数）。"""
    if not contexts:
        return 0.0
    try:
        model = await get_judge_model()
        tpl, _ = await get_prompt("judge_context_precision")
        ctx_text = "\n".join(f"[{i}] {str(c.get('content', ''))[:200]}" for i, c in enumerate(contexts, start=1))
        resp = await model.ainvoke(render_prompt(tpl, query=question, contexts=ctx_text))
        data = parse_json_loose(resp.content)
        scores = data.get("scores")
        if isinstance(scores, list) and scores:
            vals = [1.0 if str(s).strip() in ("1", "1.0", "true", "True") else 0.0 for s in scores]
            return _clip01(sum(vals) / len(vals))
        n = _first_number(resp.content)
        return _clip01(n) if n is not None else 0.0
    except Exception:
        return 0.0


async def judge_faithfulness(answer: str, contexts: list[dict]) -> float:
    """裁判判断答案关键论断被参考资料支撑的比例。"""
    if not (answer or "").strip():
        return 0.0
    try:
        model = await get_judge_model()
        tpl, _ = await get_prompt("judge_faithfulness")
        ctx_text = "\n".join(f"[{i}] {str(c.get('content', ''))[:300]}" for i, c in enumerate(contexts, start=1))
        resp = await model.ainvoke(render_prompt(tpl, query="", context=ctx_text, answer=answer[:1500]))
        n = _first_number(resp.content)
        return _clip01(n) if n is not None else 0.0
    except Exception:
        return 0.0


async def judge_answer_relevancy(question: str, answer: str) -> float:
    """裁判判断答案是否切题。"""
    if not (answer or "").strip():
        return 0.0
    try:
        model = await get_judge_model()
        tpl, _ = await get_prompt("judge_answer_relevancy")
        resp = await model.ainvoke(render_prompt(tpl, query=question, answer=answer[:1500]))
        n = _first_number(resp.content)
        return _clip01(n) if n is not None else 0.0
    except Exception:
        return 0.0


async def judge_case(question: str, answer: str, contexts: list[dict],
                     expected_ids: list[int], retrieved_ids: list[int]) -> dict:
    """单条用例完整评测：返回四指标与综合分（等权平均）。"""
    recall = context_recall(expected_ids, retrieved_ids)
    precision = await judge_context_precision(question, contexts)
    faith = await judge_faithfulness(answer, contexts)
    relev = await judge_answer_relevancy(question, answer)
    overall = _clip01((recall + precision + faith + relev) / 4.0)
    return {
        "recall": recall,
        "precision": precision,
        "faithfulness": faith,
        "relevancy": relev,
        "overall": overall,
    }
