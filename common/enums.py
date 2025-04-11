from enum import unique

from common.types import IntEnumMore, StrEnumMore
from common.constant.messages import (
    FailedMsg,
    SuccessMsg,
    ForbiddenMsg,
    UnauthorizedMsg,
    ExportDataNullMsg,
    RequestLimitedMsg,
    InternalServerErrorMsg,
)


@unique
class ResponseCodeEnum(IntEnumMore):
    """业务响应代码, 除了500之外都在200的前提下返回对应code."""

    # 唯一成功响应
    success = (0, SuccessMsg)

    # custom error code
    failed = (-1, FailedMsg)

    # http error code
    internal_error = (500, InternalServerErrorMsg)
    unauthorized = (401, UnauthorizedMsg)
    forbidden = (403, ForbiddenMsg)
    request_limited = (429, RequestLimitedMsg)


@unique
class ResponseHeaderKeyEnum(StrEnumMore):
    """响应头key"""

    request_id = ("X-Request-Id", "请求唯一ID")
    process_time = ("X-Process-Time", "请求处理时间")  # ms


@unique
class RequestHeaderKeyEnum(StrEnumMore):
    """请求头key"""

    front_scene = ("X-Front-Scene", "请求的系统标识")
    front_version = ("X-Front-Version", "版本号")


@unique
class InfoLoggerNameEnum(StrEnumMore):
    """统计数据相关日志名称."""

    # 请求相关日志
    info_request_logger = ("_info.request", "请求数据统计日志")
    info_websocket_access_logger = ("_info.websocket.access", "websocket日志")


@unique
class ContextKeyEnum(StrEnumMore):
    """上下文变量key."""

    # plugins
    request_id = ("request_id", "请求ID")
    request_start_timestamp = ("request_start_timestamp", "请求开始时间")
    request_body = ("request_body", "请求体")
    process_time = ("process_time", "请求处理时间/ms")

    # custom
    response_code = ("response_code", "响应code")
    response_data = ("response_data", "响应数据")  #  只记录code != 0 的


class TokenSceneTypeEnum(StrEnumMore):
    """token场景"""

    general = ("General", "通用")
    web = ("Web", "网页端")
    mobile = ("Mobile", "移动端")
    ios = ("Ios", "Ios")
    android = ("Android", "Android")
    wmp = ("WMP", "微信小程序")
    unknown = ("Unknown", "未知")
