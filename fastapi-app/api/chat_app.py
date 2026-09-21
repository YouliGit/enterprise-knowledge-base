"""问答应用管理"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import AppKbRel, ChatApp, KnowledgeBase, PromptTemplate, User

router = APIRouter(tags=["问答应用"])


class AppIn(BaseModel):
    name: str
    description: str = ""
    prompt_template_id: int | None = None
    model_config_id: int | None = None
    retrieval_strategy_id: int | None = None
    max_history: int = 3
    show_ref: int = 1
    use_agent: int = 1
    enabled: int = 1


@router.get("/chatApp/page")
async def page(query: str = Query(""), page: int = 1, page_size: int = 10, _: User = Depends(get_current_user)):
    qs = ChatApp.all()
    if query:
        qs = qs.filter(name__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    for it in items:
        kb_ids = [r.kb_id for r in await AppKbRel.filter(app_id=it["id"]).all()]
        it["kb_ids"] = kb_ids
        kbs = await KnowledgeBase.filter(id__in=kb_ids).values("id", "name") if kb_ids else []
        it["kb_names"] = "、".join(k["name"] for k in kbs)
        if it.get("prompt_template_id"):
            t = await PromptTemplate.filter(id=it["prompt_template_id"]).first()
            it["prompt_name"] = t.name if t else ""
        else:
            it["prompt_name"] = "默认模板"
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.get("/chatApp/options")
async def options(_: User = Depends(get_current_user)):
    rows = await ChatApp.filter(enabled=1).order_by("id").values("id", "name", "description")
    return ok(rows)


@router.post("/chatApp")
async def create(body: AppIn, user: User = Depends(get_current_user)):
    app = await ChatApp.create(owner_id=user.id, **body.model_dump())
    return ok({"id": app.id})


@router.put("/chatApp/{aid}")
async def update(aid: int, body: AppIn, _: User = Depends(get_current_user)):
    app = await ChatApp.filter(id=aid).first()
    if not app:
        raise BizException("应用不存在")
    await app.update_from_dict(body.model_dump()).save()
    return ok()


@router.put("/chatApp/{aid}/kbs")
async def bind_kbs(aid: int, body: dict, _: User = Depends(get_current_user)):
    """绑定知识库集合"""
    app = await ChatApp.filter(id=aid).first()
    if not app:
        raise BizException("应用不存在")
    kb_ids = [int(x) for x in (body.get("kb_ids") or [])]
    await AppKbRel.filter(app_id=aid).delete()
    for kb_id in kb_ids:
        if await KnowledgeBase.filter(id=kb_id).exists():
            await AppKbRel.create(app_id=aid, kb_id=kb_id)
    return ok()


@router.delete("/chatApp/{aid}")
async def remove(aid: int, _: User = Depends(get_current_user)):
    app = await ChatApp.filter(id=aid).first()
    if not app:
        raise BizException("应用不存在")
    await AppKbRel.filter(app_id=aid).delete()
    await app.delete()
    return ok()
