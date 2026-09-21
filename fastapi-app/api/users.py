"""管理员与用户管理 + 操作日志"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from common.deps import require_admin
from common.exceptions import BizException
from common.response import ok
from common.security import hash_password
from common.utils import clean_row, get_page, page_query
from models import OperationLog, User

router = APIRouter(tags=["用户管理"])


class UserIn(BaseModel):
    username: str = ""
    password: str = ""
    nickname: str = ""
    role: str = "user"
    email: str = ""
    phone: str = ""
    status: int = 1


@router.get("/admin/user/page")
async def user_page(query: str = Query(""), page: int = 1, page_size: int = 10,
                    _: User = Depends(require_admin)):
    qs = User.all()
    if query:
        from tortoise.expressions import Q
        qs = qs.filter(Q(username__icontains=query, nickname__icontains=query, join_type="OR"))
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(qs, p, ps, off)
    return ok({"list": [clean_row(i) for i in items], "total": total, "page": p, "page_size": ps})


@router.post("/admin/user")
async def user_create(body: UserIn, _: User = Depends(require_admin)):
    username = body.username.strip()
    if len(username) < 2:
        raise BizException("账号至少2个字符")
    if len(body.password) < 4:
        raise BizException("密码至少4位")
    if await User.filter(username=username).exists():
        raise BizException("账号已存在")
    user = await User.create(
        username=username, password=hash_password(body.password), nickname=body.nickname or username,
        role=body.role if body.role in ("admin", "user") else "user",
        email=body.email, phone=body.phone, status=body.status,
    )
    return ok(clean_row({"id": user.id, "username": user.username}))


@router.put("/admin/user/{uid}")
async def user_update(uid: int, body: UserIn, _: User = Depends(require_admin)):
    user = await User.filter(id=uid).first()
    if not user:
        raise BizException("用户不存在")
    user.nickname = body.nickname or user.nickname
    user.email = body.email
    user.phone = body.phone
    if body.role in ("admin", "user"):
        user.role = body.role
    if body.status in (0, 1):
        user.status = body.status
    await user.save()
    return ok()


@router.put("/admin/user/{uid}/status")
async def user_status(uid: int, body: dict, _: User = Depends(require_admin)):
    user = await User.filter(id=uid).first()
    if not user:
        raise BizException("用户不存在")
    user.status = 1 if body.get("status") == 1 else 0
    await user.save()
    return ok()


@router.put("/admin/user/{uid}/password")
async def user_reset_password(uid: int, body: dict, _: User = Depends(require_admin)):
    user = await User.filter(id=uid).first()
    if not user:
        raise BizException("用户不存在")
    pwd = str(body.get("password", ""))
    if len(pwd) < 4:
        raise BizException("密码至少4位")
    user.password = hash_password(pwd)
    await user.save()
    return ok()


@router.delete("/admin/user/{uid}")
async def user_delete(uid: int, admin: User = Depends(require_admin)):
    if uid == admin.id:
        raise BizException("不能删除自己")
    user = await User.filter(id=uid).first()
    if not user:
        raise BizException("用户不存在")
    await user.delete()
    return ok()


@router.get("/operationLog/page")
async def oplog_page(page: int = 1, page_size: int = 20, _: User = Depends(require_admin)):
    p, ps, off = get_page({"page": page, "page_size": page_size})
    total, items = await page_query(OperationLog.all(), p, ps, off)
    return ok({"list": items, "total": total, "page": p, "page_size": ps})
