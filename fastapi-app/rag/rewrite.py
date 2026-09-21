"""Query 改写：多查询扩展 / 指代消解 / HyDE（假设性文档）。"""
import json
import re

from rag.llm import get_chat_model, get_prompt, render_prompt


def _extract_lines(raw: str, limit: int = 3) -> list[str]:
    out = []
    for line in re.split(r"[\n]+", raw or ""):
        line = re.sub(r"^\s*[\d\.\)、\-\*]+\s*", "", line.strip()).strip()
        line = line.strip('"“”')
        if line:
            out.append(line)
        if len(out) >= limit:
            break
    return out


async def multi_query_expand(query: str) -> list[str]:
    """多查询扩展：LLM 把问题改写成 3 个不同表述，覆盖同义词。"""
    try:
        model = await get_chat_model()
        tpl, _ = await get_prompt("rewrite_multi_query")
        resp = await model.ainvoke(render_prompt(tpl, query=query))
        return _extract_lines(resp.content)
    except Exception:
        return []


async def coref_resolve(query: str, history: list[dict]) -> str:
    """指代消解：结合历史把「它/这个」等改写为独立完整的查询。"""
    try:
        history_text = "\n".join(
            f"{'用户' if m.get('role') == 'user' else '助手'}: {m.get('content', '')[:200]}"
            for m in (history or [])[-4:]
        )
        model = await get_chat_model(temperature=0)
        tpl, _ = await get_prompt("rewrite_coref")
        resp = await model.ainvoke(render_prompt(tpl, query=query, history=history_text or "（无）"))
        return (resp.content or "").strip()
    except Exception:
        return query


async def hyde_document(query: str) -> str:
    """HyDE：让模型先写一段假设性答案文档，用它去检索（向量对文本相似，比对问题相似更稳）。"""
    try:
        model = await get_chat_model(temperature=0)
        tpl, _ = await get_prompt("hyde_generate")
        resp = await model.ainvoke(render_prompt(tpl, query=query))
        return (resp.content or "").strip()
    except Exception:
        return ""


def parse_json_loose(raw: str) -> dict:
    """宽松 JSON 解析：截取首个 {...} 块。"""
    if not raw:
        return {}
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}
