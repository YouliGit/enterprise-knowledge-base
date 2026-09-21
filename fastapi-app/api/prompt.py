"""Prompt模板：所有发给模型的提示词在这里维护，改完立刻生效；支持写入内置模板"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from tortoise.expressions import Q

from common.deps import require_admin
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import PromptTemplate, User
from rag.llm import FALLBACK_PROMPTS

router = APIRouter(tags=["Prompt模板"])

BUILTIN_NAMES = {
    "qa_answer_concise": "简洁问答模板",
    "qa_answer_step": "分步骤回答模板",
    "qa_answer_with_source": "带出处引用模板",
    "rewrite_multi_query": "多查询扩展模板",
    "rewrite_coref": "指代消解模板",
    "hyde_generate": "HyDE假设文档模板",
    "agent_evaluate_context": "Agent召回评估模板",
    "agent_self_check": "Agent答案自查模板",
    "judge_context_precision": "评测裁判-ContextPrecision模板",
    "judge_faithfulness": "评测裁判-Faithfulness模板",
    "judge_answer_relevancy": "评测裁判-AnswerRelevancy模板",
}


class PromptIn(BaseModel):
    code: str
    name: str = ""
    scene: str = "qa"
    content: str
    enabled: int = 1
    remark: str = ""


@router.get("/prompt/page")
async def page(query: str = Query(""), page: int = 1, page_size: int = 20, _: User = Depends(require_admin)):
    qs = PromptTemplate.all()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.post("/prompt")
async def create(body: PromptIn, _: User = Depends(require_admin)):
    if not body.code.strip():
        raise BizException("编码不能为空")
    if await PromptTemplate.filter(code=body.code).exists():
        raise BizException("编码已存在")
    data = body.model_dump()
    data["name"] = data.get("name") or data["code"]
    tpl = await PromptTemplate.create(**data)
    return ok({"id": tpl.id})


@router.put("/prompt/{pid}")
async def update(pid: int, body: PromptIn, _: User = Depends(require_admin)):
    tpl = await PromptTemplate.filter(id=pid).first()
    if not tpl:
        raise BizException("模板不存在")
    await tpl.update_from_dict(body.model_dump()).save()
    return ok()


@router.delete("/prompt/{pid}")
async def remove(pid: int, _: User = Depends(require_admin)):
    tpl = await PromptTemplate.filter(id=pid).first()
    if tpl:
        await tpl.delete()
    return ok()


@router.post("/prompt/import_builtin")
async def import_builtin(_: User = Depends(require_admin)):
    """写入内置模板：存在则跳过"""
    created = 0
    for code, content in FALLBACK_PROMPTS.items():
        if await PromptTemplate.filter(code=code).exists():
            continue
        scene = "judge" if code.startswith("judge") else ("agent" if code.startswith("agent") else ("rewrite" if code.startswith(("rewrite", "hyde")) else "qa"))
        await PromptTemplate.create(
            code=code, name=BUILTIN_NAMES.get(code, code), scene=scene,
            content=content, enabled=1, remark="内置模板",
        )
        created += 1
    return ok({"created": created})
