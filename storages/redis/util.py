from common.utils import generate_random_string
from configs.config import local_configs
from configs.defines import ConnectionNameEnum
from common.responses import ResponseCodeEnum
from common.exceptions import ApiException


async def generate_captcha_code(
    unique_key: str,
    length: int,
    all_digits: bool = False,
    excludes: list[str] | None = None,
    expire_seconds: int = 60 * 5,
) -> str:
    # if await AsyncRedisUtil.get(unique_key):
    #     raise ApiException(
    #         message=RequestLimitedMsg,
    #         code=ResponseCodeEnum.request_limited.value,  # type: ignore
    #     )
    code = generate_random_string(length, all_digits, excludes)
    async with local_configs.redis.get_redis(ConnectionNameEnum.user_center) as r:
        if await r.get(unique_key):
            raise ApiException(
                message="验证码太频繁",
                code=ResponseCodeEnum.request_limited.value,  # type: ignore
            )
        await r.set(
            unique_key,
            code,
            ex=expire_seconds,
        )
    return code


async def verify_captcha_code(unique_key: str, code: str) -> bool:
    async with local_configs.redis.get_redis(ConnectionNameEnum.user_center) as r:
        cached_code = await r.get(unique_key)
        if not cached_code:
            return False
        cached_code = str(cached_code)
        result: bool = cached_code.lower() == code.lower()
        if result:
            await r.delete(unique_key)
    return result
