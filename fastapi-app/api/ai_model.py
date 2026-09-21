"""AI模型配置：对话/向量/重排三类，改配置立刻生效不用重启；测试验证连通性"""
import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import require_admin
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import AiModelConfig, User

router = APIRouter(tags=["AI模型配置"])

TYPE_NAME = {"chat": "对话", "embedding": "向量", "rerank": "重排"}


class ModelIn(BaseModel):
    name: str
    type: str = "chat"
    model: str
    vendor: str = "dashscope"
    api_base: str = ""
    api_key: str = ""
    dimension: int = 0
    temperature: float = 0.7
    enabled: int = 1
    remark: str = ""


@router.get("/aiModel/page")
async def page(type: str = Query(""), page: int = 1, page_size: int = 20, _: User = Depends(require_admin)):
    qs = AiModelConfig.all()
    if type:
        qs = qs.filter(type=type)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    for it in items:
        it["type_name"] = TYPE_NAME.get(it["type"], it["type"])
        it["has_key"] = bool(it.pop("api_key", ""))
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


@router.post("/aiModel")
async def create(body: ModelIn, _: User = Depends(require_admin)):
    if body.type not in TYPE_NAME:
        raise BizException("类型必须是 chat/embedding/rerank")
    if not body.model:
        raise BizException("模型名不能为空")
    cfg = await AiModelConfig.create(**body.model_dump())
    return ok({"id": cfg.id})


@router.put("/aiModel/{mid}")
async def update(mid: int, body: ModelIn, _: User = Depends(require_admin)):
    cfg = await AiModelConfig.filter(id=mid).first()
    if not cfg:
        raise BizException("配置不存在")
    data = body.model_dump()
    if not data.get("api_key"):
        data.pop("api_key")  # 前端未填则保留旧 Key
    await cfg.update_from_dict(data).save()
    return ok()


@router.delete("/aiModel/{mid}")
async def remove(mid: int, _: User = Depends(require_admin)):
    cfg = await AiModelConfig.filter(id=mid).first()
    if cfg:
        await cfg.delete()
    return ok()


@router.put("/aiModel/{mid}/enable")
async def enable(mid: int, body: dict, _: User = Depends(require_admin)):
    cfg = await AiModelConfig.filter(id=mid).first()
    if not cfg:
        raise BizException("配置不存在")
    cfg.enabled = 1 if body.get("enabled") == 1 else 0
    await cfg.save()
    return ok()


@router.post("/aiModel/{mid}/test")
async def test(mid: int, _: User = Depends(require_admin)):
    """连通性测试：对话回环问答 / 向量查维度 / 重排看返回分数，记录耗时"""
    cfg = await AiModelConfig.filter(id=mid).first()
    if not cfg:
        raise BizException("配置不存在")
    t0 = time.time()
    try:
        if cfg.type == "chat":
            from rag.llm import get_chat_model

            model = await get_chat_model(cfg_id=mid, temperature=0)
            resp = await model.ainvoke("请只回复两个字：正常")
            info = f"正常 (回复: {str(resp.content)[:20]})"
        elif cfg.type == "embedding":
            from rag.llm import get_embedding_model

            emb, dim = await get_embedding_model(cfg_id=mid)
            vec = await emb.aembed_query("连通性测试")
            info = f"正常 (返回 {len(vec)} 维，配置 {dim} 维)"
            if len(vec) != dim:
                raise RuntimeError(f"维度不匹配：模型返回 {len(vec)} 维，配置 {dim} 维")
        else:
            from rag.llm import get_reranker

            reranker = await get_reranker(cfg_id=mid)
            results = await reranker.rerank_texts("什么是光模块", ["光模块用于光电信号转换", "今天天气不错"], top_n=2)
            top = max((r["relevance_score"] for r in results), default=0.0)
            info = f"重排返回{len(results)}条，最高分{round(top, 4)}"
        cost = int((time.time() - t0) * 1000)
        cfg.test_info = f"{info} (耗时{cost}ms)"
        await cfg.save()
        return ok({"ok": True, "info": cfg.test_info})
    except Exception as e:
        cost = int((time.time() - t0) * 1000)
        cfg.test_info = f"失败: {str(e)[:200]}"
        await cfg.save()
        return ok({"ok": False, "info": cfg.test_info, "cost_ms": cost})
