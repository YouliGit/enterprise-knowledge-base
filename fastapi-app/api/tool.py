"""工具中心：内置工具写入 / 手动执行测试 / 工具调用日志"""
import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from tortoise.expressions import Q

from common.deps import require_admin
from common.exceptions import BizException
from common.response import ok
from common.utils import get_page, page_query
from models import Tool, ToolCallLog, User
from rag.tools import _normalize_schema, execute_tool, import_builtin_tools

router = APIRouter(tags=["工具中心"])


class ToolIn(BaseModel):
    code: str
    name: str
    description: str = ""
    schema_json: str = "{}"
    handler: str = ""
    enabled: int = 1


@router.get("/tool/page")
async def page(query: str = Query(""), page: int = 1, page_size: int = 20, _: User = Depends(require_admin)):
    qs = Tool.all()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    return ok({"list": items, "total": total, "page": p, "page_size": ps})


def _validate_schema(schema_json: str):
    """校验工具 schema：必须是合法 JSON，且能规范化为带 name 的 function 定义。

    拦住 {}、缺 name 之类的脏数据——它们会让 bind_tools 抛
    "Unsupported function {}"，进而拖垮整个问答与 Agent 链路。
    """
    try:
        json.loads(schema_json or "{}")
    except Exception:
        raise BizException("schema_json 不是合法 JSON")
    if not _normalize_schema(schema_json):
        raise BizException("schema_json 需包含 function.name（或顶层 name），且必须是 JSON 对象")


@router.post("/tool")
async def create(body: ToolIn, _: User = Depends(require_admin)):
    if await Tool.filter(code=body.code).exists():
        raise BizException("工具编码已存在")
    _validate_schema(body.schema_json)
    tool = await Tool.create(built_in=0, **body.model_dump())
    return ok({"id": tool.id})


@router.put("/tool/{tid}")
async def update(tid: int, body: ToolIn, _: User = Depends(require_admin)):
    tool = await Tool.filter(id=tid).first()
    if not tool:
        raise BizException("工具不存在")
    _validate_schema(body.schema_json)
    await tool.update_from_dict(body.model_dump()).save()
    return ok()


@router.delete("/tool/{tid}")
async def remove(tid: int, _: User = Depends(require_admin)):
    tool = await Tool.filter(id=tid).first()
    if tool:
        if tool.built_in == 1:
            raise BizException("内置工具不可删除，可停用")
        await tool.delete()
    return ok()


@router.post("/tool/import_builtin")
async def import_builtin(_: User = Depends(require_admin)):
    """写入内置工具"""
    created = await import_builtin_tools()
    return ok({"created": created})


@router.post("/tool/execute")
async def execute(body: dict, _: User = Depends(require_admin)):
    """手动测试工具"""
    code = str(body.get("code", ""))
    if not code:
        raise BizException("缺少 code")
    args = body.get("args") or {}
    result = await execute_tool(code, args)
    return ok({"result": result})


@router.get("/tool/log/page")
async def log_page(query: str = Query(""), page: int = 1, page_size: int = 20, _: User = Depends(require_admin)):
    qs = ToolCallLog.all()
    if query:
        qs = qs.filter(tool_code__icontains=query)
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    return ok({"list": items, "total": total, "page": p, "page_size": ps})
