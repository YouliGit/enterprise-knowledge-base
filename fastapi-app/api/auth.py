"""登录注册、个人资料、修改密码"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from common.deps import get_current_user
from common.exceptions import BizException
from common.response import ok
from common.security import create_token, hash_password, verify_password
from common.utils import clean_row
from models import OperationLog, User

router = APIRouter(tags=["登录注册"])


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    nickname: str = ""


class ProfileIn(BaseModel):
    nickname: str = ""
    email: str = ""
    phone: str = ""
    avatar: str = ""


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


def _user_data(user: User, token: str | None = None) -> dict:
    data = clean_row({
        "id": user.id, "username": user.username, "nickname": user.nickname,
        "avatar": user.avatar, "role": user.role, "email": user.email,
        "phone": user.phone, "status": user.status,
    })
    if token:
        data["token"] = token
    return data


@router.post("/login")
async def login(body: LoginIn, request: Request):
    user = await User.filter(username=body.username.strip()).first()
    if not user or not verify_password(body.password, user.password):
        await OperationLog.create(username=body.username, action="登录失败", detail="账号或密码错误",
                                  ip=request.client.host if request.client else "")
        raise BizException("账号或密码错误")
    if user.status != 1:
        raise BizException("账号已被禁用，请联系管理员")
    token = create_token(user.id, user.username, user.role)
    await OperationLog.create(user_id=user.id, username=user.username, action="登录", ip=request.client.host if request.client else "")
    return ok(_user_data(user, token))


@router.post("/register")
async def register(body: RegisterIn):
    username = body.username.strip()
    if len(username) < 2:
        raise BizException("账号至少2个字符")
    if len(body.password) < 4:
        raise BizException("密码至少4位")
    if await User.filter(username=username).exists():
        raise BizException("该账号已被注册")
    user = await User.create(
        username=username, password=hash_password(body.password),
        nickname=body.nickname.strip() or username, role="user",
    )
    token = create_token(user.id, user.username, user.role)
    return ok(_user_data(user, token))


@router.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return ok(_user_data(user))


@router.put("/auth/profile")
async def update_profile(body: ProfileIn, user: User = Depends(get_current_user)):
    user.nickname = body.nickname.strip() or user.nickname
    user.email = body.email
    user.phone = body.phone
    if body.avatar:
        user.avatar = body.avatar
    await user.save()
    return ok(_user_data(user))


@router.put("/auth/password")
async def change_password(body: PasswordIn, user: User = Depends(get_current_user)):
    if not verify_password(body.old_password, user.password):
        raise BizException("原密码不正确")
    if len(body.new_password) < 4:
        raise BizException("新密码至少4位")
    user.password = hash_password(body.new_password)
    await user.save()
    return ok()
