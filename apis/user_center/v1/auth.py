from datetime import timedelta

from fastapi import Depends, Request, APIRouter

from storages import enums
from common.utils import datetime_now
from service.crud import obj_prefetch_fields
from common.encrypt import PasswordUtil
from configs.config import local_configs
from storages.redis import keys
from common.responses import Resp
from service.auth.impl import (
    code_login,
    password_login,
    login_cache_redis,
    logout_cache_redis,
)
from storages.redis.util import verify_captcha_code
from service.auth.schemas import (
    LoginResponse,
    CodeLoginSchema,
    ResetPasswordIn,
    ChangePasswordIn,
    PasswordLoginSchema,
)
from service.dependencies import token_required
from service.account.schema import AccountList, AccountDetail
from storages.relational.models.user_center import Account

router = APIRouter()


@router.post(
    "/login/pwd",
    summary="登录",
    description="登录接口",
)
async def login(request: Request, login_data: PasswordLoginSchema) -> Resp[LoginResponse]:
    account = await password_login(login_data)
    token = await login_cache_redis(account, login_data.scene)

    return Resp[LoginResponse](
        data=LoginResponse(
            account=AccountList.model_validate(account),
            token=token,
            expired_at=datetime_now() + timedelta(seconds=local_configs.server.token_expire_seconds),
        ),
    )


@router.post(
    "/login/code",
    summary="登录",
    description="登录接口",
)
async def login(request: Request, login_data: CodeLoginSchema) -> Resp[LoginResponse]:
    account = await code_login(login_data)
    token = await login_cache_redis(account, login_data.scene)

    return Resp[LoginResponse](
        data=LoginResponse(
            account=AccountList.model_validate(account),
            token=token,
            expired_at=datetime_now() + timedelta(seconds=local_configs.server.token_expire_seconds),
        ),
    )


@router.post(
    "/logout",
    summary="登出",
    description="退出登录接口",
)
async def logout(
    request: Request,
    scene: enums.TokenSceneTypeEnum,
    account: Account = Depends(token_required),
) -> Resp:
    await logout_cache_redis(account, scene)
    return Resp()


@router.get(
    "/myself",
    summary="个人信息",
    description="获取个人信息",
)
async def myself_account_detail(
    request: Request,
    account: Account = Depends(token_required),
) -> AccountDetail:
    account = await obj_prefetch_fields(account, AccountDetail)

    return Resp[AccountDetail](data=account)


@router.post(
    "/password/reset",
    summary="密码重置",
    description="密码重置接口",
)
async def reset_password(request: Request, schema: ResetPasswordIn) -> Resp:
    account = await Account.get_by_identifier(schema.identifier)
    if not account:
        return Resp.fail(message="账号未注册")

    code = schema.code
    unique_key = keys.UserCenterKey.CodeUniqueKey.format(  # type: ignore
        scene=enums.SendCodeScene.reset_password.value,
        identifier=str(account.id),
    )

    if not await verify_captcha_code(
        unique_key=unique_key,
        code=code,
    ):
        return Resp.fail(message="验证码错误")

    account.password = PasswordUtil.get_password_hash(schema.password)
    await account.save(update_fields=["password"])

    return Resp()


@router.post(
    "/password/change",
    summary="修改密码",
    description="修改密码",
)
async def change_password(
    request: Request,
    schema: ChangePasswordIn,
    account: Account = Depends(token_required),
) -> Resp:
    if not PasswordUtil.verify_password(
        schema.old_password,
        account.password,
    ):
        return Resp.fail(message="旧密码错误")
    account.password = PasswordUtil.get_password_hash(schema.new_password)
    await account.save(update_fields=["password"])

    return Resp()
