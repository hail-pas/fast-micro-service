import time
from uuid import UUID
from typing import Annotated
from collections.abc import Callable

from loguru import logger
from fastapi import Body, Query, Header, Depends, Request
from pydantic import PositiveInt
from cachetools import TTLCache
from redis.asyncio import Redis, ConnectionPool
from tortoise.models import Model
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param
from tortoise.contrib.pydantic import PydanticModel

from common.enums import ResponseCodeEnum, RequestHeaderKeyEnum
from common.utils import datetime_now
from common.encrypt import HashUtil
from common.schemas import Pager, CRUDPager
from configs.config import local_configs
from storages.redis import keys
from configs.defines import ConnectionNameEnum
from service.exceptions import ApiException
from common.constant.messages import (
    ForbiddenMsg,
    AuthorizationHeaderInvalidMsg,
    AuthorizationHeaderMissingMsg,
    AuthorizationHeaderTypeErrorMsg,
)
from storages.relational.models.user_center import Account


class TheBearer(HTTPBearer):
    async def __call__(
        self: "TheBearer",
        request: Request,  # WebSocket
    ) -> HTTPAuthorizationCredentials:  # _authorization: Annotated[Optional[str], Depends(oauth2_scheme)]
        authorization: str | None = request.headers.get("Authorization")
        if not authorization:
            raise ApiException(
                code=ResponseCodeEnum.unauthorized,
                message=AuthorizationHeaderMissingMsg,
            )
        scheme, credentials = get_authorization_scheme_param(authorization)
        if not (authorization and scheme and credentials):
            raise ApiException(
                code=ResponseCodeEnum.unauthorized,
                message=AuthorizationHeaderInvalidMsg,
            )
        if scheme != "Bearer" and self.auto_error:
            raise ApiException(
                code=ResponseCodeEnum.unauthorized,
                message=AuthorizationHeaderTypeErrorMsg,
            )
        return HTTPAuthorizationCredentials(
            scheme=scheme,
            credentials=credentials,
        )


auth_schema = TheBearer()


def pure_get_pager(
    page: PositiveInt = Query(default=1, examples=[1], description="第几页"),
    size: PositiveInt = Query(default=10, examples=[10], description="每页数量"),
) -> Pager:
    return Pager(limit=size, offset=(page - 1) * size)


def paginate(
    model: type[Model],
    search_fields: set[str],
    order_fields: set[str],
    list_schema: type[PydanticModel],
    max_limit: int | None,
    param_type: type[Query] | type[Body] = Query,
) -> Callable[[PositiveInt, PositiveInt, str, set[str], set[str] | None], CRUDPager]:
    def get_pager(
        page: PositiveInt = param_type(default=1, examples=[1], description="第几页"),
        size: PositiveInt = param_type(default=10, examples=[10], description="每页数量"),
        search: str = param_type(
            None,
            description="搜索关键字."
            + (f" 匹配字段: {', '.join(search_fields)}" if search_fields else "无可匹配的字段"),  # ruff: noqa: E501
        ),
        order_by: set[str] = param_type(
            default=set(),
            # examples=["-id"],
            description=(
                "排序字段. 升序保持原字段名, 降序增加前缀-."
                + (f" 可选字段: {', '.join(order_fields)}" if order_fields else " 无可排序字段")  # ruff: noqa: E501
            ),
        ),
        selected_fields: set[str] = param_type(
            default=set(),
            description=f"指定返回字段. 可选字段: {', '.join(list_schema.model_fields.keys())}",
        ),
    ) -> CRUDPager:
        if max_limit is not None:
            size = min(size, max_limit)
        for field in order_by:
            if field.startswith("-"):
                field = field[1:]  # noqa

            if hasattr(model, "model_fields"):
                available_order_fields = model.model_fields.keys()
            else:
                available_order_fields = model._meta.db_fields

            if field not in available_order_fields:
                raise ApiException(
                    "排序字段不存在",
                )
        if selected_fields:
            selected_fields.add("id")

        if page <= 0:
            raise ApiException(
                "页码必须大于0",
            )
        if size <= 0:
            raise ApiException(
                "每页数量必须大于0",
            )
        return CRUDPager(
            limit=size,
            offset=(page - 1) * size,
            order_by=set(
                filter(lambda i: i.split("-")[-1] in order_fields, order_by),
            ),
            search=search,
            selected_fields=selected_fields,
            available_search_fields=search_fields,
            list_schema=list_schema,
        )

    return get_pager


_account_cache = TTLCache(maxsize=256, ttl=60)


async def _get_account_by_id(account_id: UUID) -> Account:
    if account_id in _account_cache:
        return _account_cache[account_id]
    acc = await Account.get_or_none(id=account_id, deleted_at=0)
    if not acc:
        raise ApiException(
            code=ResponseCodeEnum.unauthorized,
            message="Invalid Account",
        )
    _account_cache[account_id] = acc
    return acc


async def _validate_jwt_token(
    request: Request,
    token: HTTPAuthorizationCredentials,
    user_center_redis_conn_pool: ConnectionPool,
) -> Account:
    async with Redis(
        connection_pool=user_center_redis_conn_pool,
        single_connection_client=True,
        decode_responses=True,
    ) as redis:
        token_identidier = await redis.get(
            keys.UserCenterKey.Token2AccountKey.format(  # type: ignore
                token=token.credentials,
            ),
        )

        if not token_identidier:
            logger.warning("token缓存失效")
            raise ApiException(
                code=ResponseCodeEnum.unauthorized.value,
                message="登录失效或已在其他地方登录",
            )

        account_id, scene = token_identidier.split(":")

        if request.headers.get(RequestHeaderKeyEnum.front_scene.value) and scene != request.headers.get(
            RequestHeaderKeyEnum.front_scene.value,
        ):
            logger.warning("token场景不匹配")
            raise ApiException(
                code=ResponseCodeEnum.unauthorized.value,
                message="token异常使用",
            )

        account = await _get_account_by_id(account_id)

        if not account:
            logger.warning("token账户不存在")
            raise ApiException(
                code=ResponseCodeEnum.unauthorized.value,
                message=AuthorizationHeaderInvalidMsg,
            )

        # set scope
        request.scope["user"] = account
        request.scope["scene"] = scene
        request.scope["is_staff"] = account.is_staff
        request.scope["is_super_admin"] = account.is_super_admin
        return account


class TokenRequired:
    def __init__(
        self,
        user_center_redis_conn_pool: ConnectionPool,
    ) -> None:
        self.user_center_redis_conn_pool = user_center_redis_conn_pool

    async def __call__(
        self,
        request: Request,  # WebSocket
        token: Annotated[HTTPAuthorizationCredentials, Depends(auth_schema)],
    ) -> Account:
        return await _validate_jwt_token(
            request,
            token,
            self.user_center_redis_conn_pool,
        )


token_required = TokenRequired(local_configs.redis.connection_pool(ConnectionNameEnum.user_center))


class ApiPermissionCheck:
    def __init__(
        self,
    ) -> None:
        pass

    async def __call__(
        self,
        request: Request,
        token: Annotated[HTTPAuthorizationCredentials, Depends(auth_schema)],
    ) -> Account:
        account: Account | None = request.scope.get("user")  # type: ignore
        if not account:
            account = await token_required(request, token)

        if account.is_super_admin:
            return account

        method = request.method
        root_path: str = request.scope["root_path"]
        path: str = request.scope["route"].path

        if await account.has_permission(
            [
                "*",
                f"{request.app.code}:*",
                f"{request.app.code}:{method}:{root_path}{path}",
            ],
        ):
            return account

        raise ApiException(
            code=ResponseCodeEnum.forbidden.value,
            message=ResponseCodeEnum.forbidden.label,
        )


api_permission_check = ApiPermissionCheck()


class SuperAdminRequired:
    def __init__(
        self,
    ) -> None:
        pass

    async def __call__(
        self,
        request: Request,
        token: Annotated[HTTPAuthorizationCredentials, Depends(auth_schema)],
    ) -> Account:
        account: Account | None = request.scope.get("user")  # type: ignore
        if not account:
            account = await token_required(request, token)

        if not account.is_super_admin:
            raise ApiException(
                code=ResponseCodeEnum.forbidden.value,
                message=ResponseCodeEnum.forbidden.label,
            )
        return account


super_admin_required = SuperAdminRequired()


class StaffAdminRequired:
    def __init__(
        self,
    ) -> None:
        pass

    async def __call__(
        self,
        request: Request,
        token: Annotated[HTTPAuthorizationCredentials, Depends(auth_schema)],
    ):
        account: Account | None = request.scope.get("user")  # type: ignore
        if not account:
            account = await token_required(request, token)

        if not account.is_staff:
            raise ApiException(
                code=ResponseCodeEnum.forbidden.value,
                message=ResponseCodeEnum.forbidden.label,
            )
        return account


staff_admin_required = StaffAdminRequired()


class ApiKeyPermissionCheck:
    """外部apikey权限校验"""

    user_center_redis_conn_pool: ConnectionPool

    def __init__(
        self,
        user_center_redis_conn_pool: ConnectionPool,
    ) -> None:
        self.user_center_redis_conn_pool = user_center_redis_conn_pool

    async def __call__(
        self,
        request: Request,
        x_api_key: str = Header(
            description="ApiKey",
        ),
        x_timestamp: int = Header(
            description="请求时间戳, 秒级时间戳, 允许误差+30s",
        ),
        x_sign: str = Header(
            description='签名, 生成: hmac_sha256(secret_key, "api_key&timestamp")',
        ),
    ) -> bool:
        if abs(int(time.time()) - int(x_timestamp)) > 30:
            raise ApiException(
                message="请求时间戳过期",
                code=ResponseCodeEnum.unauthorized.value,
            )

        redis_api_secret_key = keys.RedisCacheKey.ApiSecretKey.format(  # type: ignore
            api_key=x_api_key,
        )
        redis_perm_key = keys.RedisCacheKey.ApiKeyPermissionSet.format(  # type: ignore
            api_key=x_api_key,
        )

        async with Redis(
            connection_pool=self.user_center_redis_conn_pool,
            single_connection_client=True,
        ) as r:
            async with r.pipeline() as pipe:
                pipe.get(redis_api_secret_key)
                pipe.smismember(
                    name=redis_perm_key,
                    values=[
                        f"{request.app.code}:*",
                        f'{request.app.code}:{request.method}:{request.scope["root_path"]}{request.scope["route"].path}',
                    ],
                )
                secret_key, is_ok = await pipe.execute()
        if not secret_key:
            raise ApiException(
                message="无效的ApiKey",
                code=ResponseCodeEnum.unauthorized.value,
            )

        result_sign = HashUtil.hmac_sha256_encode(
            k=secret_key,
            s=f"{x_api_key}&{x_timestamp}",
        )
        if result_sign != x_sign:
            raise ApiException(
                message="签名错误",
                code=ResponseCodeEnum.unauthorized.value,
            )

        # 如果请求的接口，不在权限集合里
        if not any(is_ok):
            raise ApiException(
                message=ForbiddenMsg,
                code=ResponseCodeEnum.forbidden.value,
            )
        request.scope["scene"] = "ApiCall"
        request.scope["is_staff"] = False
        request.scope["is_super_admin"] = False
        request.scope["is_trial"] = False

        return True


external_api_key_permission_check = ApiKeyPermissionCheck(
    local_configs.redis.connection_pool(ConnectionNameEnum.user_center)
)
