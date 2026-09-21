"""FastAPI 依赖：登录态 / 管理员"""
from fastapi import Depends, Query, Request

from common.exceptions import AuthException
from common.security import decode_token
from models import User


def _extract_token(request: Request, token: str = Query(default="", alias="token")) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    if token:
        return token
    raise AuthException()


async def get_current_user(request: Request, raw: str = Depends(_extract_token)) -> User:
    try:
        payload = decode_token(raw)
    except Exception:
        raise AuthException()
    user = await User.filter(id=payload.get("uid")).first()
    if not user:
        raise AuthException("用户不存在")
    if user.status != 1:
        raise AuthException("账号已被禁用")
    request.state.user = user
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AuthException("需要管理员权限", code=403)
    return user
