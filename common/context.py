import time
import uuid
from typing import Any
from contextvars import ContextVar

from starlette.types import Message
from starlette_context import context
from starlette.requests import Request, HTTPConnection
from starlette.responses import Response
from starlette.datastructures import MutableHeaders
from starlette_context.plugins import Plugin

from common.log import logger
from common.enums import (
    ContextKeyEnum,
    ResponseCodeEnum,
    InfoLoggerNameEnum,
    ResponseHeaderKeyEnum,
)

request_id_var: ContextVar[str] = ContextVar(
    ContextKeyEnum.request_id.value,
)
response_code_var: ContextVar[int] = ContextVar(
    ContextKeyEnum.response_code.value,
)
response_data_var: ContextVar[dict] = ContextVar(
    ContextKeyEnum.response_data.value,
)


# enrich response 会触发两次 http.response.start、http.response.body
class RequestIdPlugin(Plugin):
    """请求唯一标识"""

    key: str = ContextKeyEnum.request_id.value
    # is_internal: bool = False

    # def __init__(self, is_internal: bool = False) -> None:
    #     self.is_internal = is_internal

    async def process_request(
        self,
        request: Request | HTTPConnection,
    ) -> Any | None:
        # if self.is_internal:
        request_id = request.headers.get(
            ResponseHeaderKeyEnum.request_id.value,
        )
        return request_id or str(uuid.uuid4())
        return str(uuid.uuid4())

    async def enrich_response(
        self,
        response: Response | Message,
    ) -> None:
        value = str(context.get(self.key))
        # for ContextMiddleware
        if isinstance(response, Response):
            response.headers[ResponseHeaderKeyEnum.request_id.value] = value
        # for ContextPureMiddleware
        else:
            if response["type"] == "http.response.start":
                headers = MutableHeaders(scope=response)
                headers.append(ResponseHeaderKeyEnum.request_id.value, value)


class RequestStartTimestampPlugin(Plugin):
    """请求开始时间"""

    key = ContextKeyEnum.request_start_timestamp.value

    async def process_request(
        self,
        request: Request | HTTPConnection,
    ) -> Any | None:
        return time.time()


class RequestProcessInfoPlugin(Plugin):
    """请求、响应相关的日志"""

    key = ContextKeyEnum.process_time.value

    async def process_request(
        self,
        request: HTTPConnection,
    ) -> Any | None:
        return {
            "method": request.scope["method"],
            "uri": request.scope["path"],
            "client": request.scope.get("client", ("", ""))[0],
        }

    async def enrich_response(
        self,
        response: Response | Message,
    ) -> None:
        request_start_timestamp = context.get(RequestStartTimestampPlugin.key)
        if not request_start_timestamp:
            raise RuntimeError("Cannot evaluate process time")
        process_time = (time.time() - float(request_start_timestamp)) * 1000  # ms
        if isinstance(response, Response):
            response.headers[ResponseHeaderKeyEnum.process_time.value] = str(
                process_time,
            )
        else:
            if response["type"] == "http.response.start":
                headers = MutableHeaders(scope=response)
                headers.append(
                    ResponseHeaderKeyEnum.process_time.value,
                    str(process_time),
                )
        info_dict = context.get(self.key)
        info_dict["process_time"] = process_time  # type: ignore
        code = context.get(ContextKeyEnum.response_code.value)
        if code is not None and code != ResponseCodeEnum.success.value:
            data = context.get(ContextKeyEnum.response_data.value)
            info_dict["response_data"] = data  # type: ignore

        logger.bind(name=InfoLoggerNameEnum.info_request_logger.value).info(info_dict)
