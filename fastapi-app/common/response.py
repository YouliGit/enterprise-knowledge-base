"""统一返回结构 {"code":0,"msg":"ok","data":...}"""
from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any = None, msg: str = "ok") -> dict:
    return {"code": 0, "msg": msg, "data": data}


def fail(msg: str = "失败", code: int = 1, data: Any = None) -> dict:
    return {"code": code, "msg": msg, "data": data}


def fail_response(msg: str = "失败", code: int = 1, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "msg": msg, "data": None})


def page_data(items: list, total: int, page: int, page_size: int) -> dict:
    return {"list": items, "total": total, "page": page, "page_size": page_size}
