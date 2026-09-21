"""统一异常处理"""
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse

from .response import fail


class BizException(Exception):
    """业务异常：msg 直接透给前端"""

    def __init__(self, msg: str, code: int = 1):
        self.msg = msg
        self.code = code
        super().__init__(msg)


class AuthException(BizException):
    def __init__(self, msg: str = "未登录或登录已过期", code: int = 401):
        super().__init__(msg, code)


async def biz_exception_handler(request: Request, exc: BizException):
    return JSONResponse(status_code=200, content=fail(exc.msg, exc.code))


async def http_exception_handler(request: Request, exc):
    return JSONResponse(status_code=200, content=fail(str(getattr(exc, "detail", exc))))


async def validation_exception_handler(request: Request, exc):
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    return JSONResponse(status_code=200, content=fail(f"参数错误: {loc} {first.get('msg', '')}"))


async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(status_code=200, content=fail(f"服务器内部错误: {type(exc).__name__}: {exc}"))
