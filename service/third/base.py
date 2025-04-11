"""三方服务"""

from __future__ import annotations

import abc
import enum
import string
import asyncio
from json import JSONDecodeError
from typing import Any, Generic, TypeVar, ParamSpec
from functools import partial
from collections.abc import Callable, Awaitable

import httpx
from loguru import logger
from pydantic import BaseModel
from starlette_context import context

from common.enums import ResponseCodeEnum, ResponseHeaderKeyEnum
from common.regex import validate_ip_or_host, only_alphabetic_numeric
from common.utils import await_in_sync
from common.context import RequestIdPlugin

DATA_SEND_WAYS = ["auto", "json", "params", "data"]
PROTOCOLS = ["http", "https"]


P = ParamSpec("P")


@enum.unique
class RequestMethodEnum(enum.Enum):
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    # OPTIONS = "options"
    # HEAD = "head"
    # CONNECT = "connect"
    # TRACE = "trace"


RawResponseType = httpx.Response

DataT = TypeVar("DataT", bound=BaseModel | str)


class Response(BaseModel, Generic[DataT]):
    success: bool = False
    status_code: int = 0  # 请求失败的情况下为0
    data: DataT | None = None
    message: str | None = None
    code: int | None = None  # 业务代码
    trace_id: str | None = None
    request_context: dict

    # @abc.abstractclassmethod
    @classmethod
    def parse_response(
        cls,
        raw_response: RawResponseType,
        request_context: dict,
    ) -> Response[Any]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"success: {self.success}, status_code: {self.status_code}"


ResponseType = TypeVar("ResponseType", bound=Response[Any])

ResponseClsType = type[Response]


class DefaultResponse(Response[DataT], Generic[DataT]):
    @classmethod
    def parse_response(
        cls,
        raw_response: RawResponseType,
        request_context: dict,
    ) -> Response[Any]:
        status_code = raw_response.status_code
        success = False
        code = status_code
        message = trace_id = None
        try:
            data = raw_response.json()
            code = data.get("code", status_code)
            message = data.get("message")
            trace_id = data.get("trace_id")
            data = data.get("data")
            if code == 0:
                success = True
        except JSONDecodeError:
            message = raw_response.text
            data = None
        return cls(
            success=success,
            status_code=status_code,
            data=data,
            message=message,
            code=code,
            trace_id=trace_id,
            request_context=request_context,
        )


class API:
    name: str
    protocol: str | None
    host: str | None
    port: int | None
    headers: dict | None
    params: dict | None
    data: dict | None
    json: dict | None
    response_cls: ResponseClsType | None
    timeout: int | None
    cookies: dict | None
    method: str
    uri: str  # /xx

    def __init__(
        self,
        name: str,
        method: str,
        uri: str,
        protocol: str | None = None,
        host: str | None = None,
        port: int | None = None,
        response_cls: ResponseClsType | None = None,
        headers: dict | None = None,
        cookies: dict | None = None,
        params: dict | None = None,
        data: dict | None = None,
        json: dict | None = None,
        timeout: int | None = None,
    ) -> None:
        assert name, "name cannot be empty"
        assert (
            only_alphabetic_numeric(name) and name[0] not in string.digits
        ), "name of api is unique identifier under third which can only contains alphabet or number or underscore"
        self.name = name
        method = method.lower()
        assert method in [m.value for m in RequestMethodEnum], f"invalid request method: {method}"
        self.method = method
        assert uri and uri.startswith("/"), "URI string must starts with '/'"
        self.uri = uri
        if protocol:
            assert protocol in PROTOCOLS, f"invalid request protocol: {protocol}"
        self.protocol = protocol
        if host:
            success, self.host = validate_ip_or_host(host)
            if not success:
                raise TypeError(f"incorrect host: {self.host}")
        else:
            self.host = None
        self.port = port
        self.headers = headers
        self.params = params
        self.data = data
        self.json = json
        self.response_cls = response_cls
        self.cookies = cookies
        self.timeout = timeout


async def default_request_proxy(request_kwargs: dict) -> RawResponseType:
    async with httpx.AsyncClient() as client:
        return await client.request(
            **request_kwargs,
        )


class Third:
    name: str
    protocol: str
    host: str
    response_cls: ResponseClsType
    _request: Callable[[dict], Awaitable[RawResponseType]]
    port: int | None
    headers: dict | None
    params: dict | None
    data: dict | None
    json: dict | None
    timeout: int | None
    cookies: dict | None
    apis: set[API] = set()
    _api_names: set[str] = set()
    # _request = requests.request
    api_key: str | None = None
    sign_key: str | None = None
    verify_ssl: bool = True

    def __init__(
        self,
        name: str,
        protocol: str,
        host: str,
        response_cls: ResponseClsType,
        port: int | None = None,
        apis: list[API] | None = None,
        headers: dict | None = None,
        params: dict | None = None,
        data: dict | None = None,
        json: dict | None = None,
        cookies: dict | None = None,
        timeout: int = 6,
        _request: Callable[
            [dict],
            Awaitable[RawResponseType],
        ] = default_request_proxy,
    ) -> None:
        assert all(
            [name, protocol, host, response_cls],
        ), f"value required parameters: {', '.join(['name', 'protocol', 'host', 'headers', 'data', 'response'])}"  # noqa
        self.name = name
        if protocol:
            assert protocol in PROTOCOLS, f"invalid request protocol: {protocol}"
        self.protocol = protocol
        if host:
            success, self.host = validate_ip_or_host(host)
            if not success:
                raise TypeError(f"incorrect host: {self.host}")
        else:
            self.host = host
        self.port = port
        self.headers = headers
        self.params = params
        self.data = data
        self.json = json
        self.response_cls = response_cls
        self.cookies = cookies
        self.timeout = timeout
        self._request = _request
        if apis:
            self.apis = set(apis)
            for api in apis:
                assert (
                    all(i in string.ascii_lowercase + string.ascii_uppercase + string.digits + "_" for i in api.name)
                    and api.name[0] not in string.digits
                ), "illegal api name"
                if api.name in self._api_names:
                    raise Exception(f"two API use the same name: {api.name}")
                setattr(self, api.name, partial(self.request, api=api))
                self._api_names.add(api.name)
        # if request:
        # self._request = request

    def register_api(self, api: API) -> None:
        assert (
            all(i in string.ascii_lowercase + string.ascii_uppercase + string.digits + "_" for i in api.name)
            and api.name[0] not in string.digits
        ), "illegal api name"
        if api.name in self._api_names:
            raise Exception(f"the {api.name} API already exists")
        self.apis.add(api)
        setattr(self, api.name, partial(self.request, api=api))

    def update_dict(
        self,
        attr_name: str,
        api: API,
        _d: BaseModel | dict | None,
    ) -> dict:
        if isinstance(_d, BaseModel):
            _d = _d.model_dump(by_alias=True)
        data = getattr(self, attr_name) or {}
        api_data = getattr(api, attr_name)
        if api_data:
            data.update(api_data)
        if _d:
            data.update(_d)
        for k, v in data.items():
            if isinstance(v, Callable):  # type: ignore
                data[k] = v()
        return data

    async def request(
        self,
        api: API,
        params: BaseModel | dict | None = None,
        data: BaseModel | dict | None = None,
        json: BaseModel | dict | None = None,
        headers: BaseModel | dict | None = None,
        cookies: BaseModel | dict | None = None,
        timeout: int | None = None,
        **kwargs,
    ) -> Response[Any]:
        protocol = api.protocol if api.protocol else self.protocol
        host = api.host if api.host else self.host
        prefix = f"{protocol}://{host}"
        port = self.port
        if api.port:
            port = api.port
        if port:
            prefix += ":" + str(port)

        request_params = self.update_dict("params", api, params)

        request_data = self.update_dict("data", api, data)

        request_json = self.update_dict("json", api, json)

        request_headers = self.update_dict("headers", api, headers)

        # 链路接续
        try:
            request_id = context.get(RequestIdPlugin.key)
            request_headers.update(
                {ResponseHeaderKeyEnum.request_id.value: request_id},
            )
        except Exception:
            ...

        request_cookies = self.update_dict("cookies", api, cookies)

        if not timeout:
            timeout = self.timeout
            if api.timeout:
                timeout = api.timeout
        response_cls: ResponseClsType = self.response_cls
        if api.response_cls is not None:
            response_cls = api.response_cls

        request_context = {
            "method": api.method,
            "url": prefix + api.uri,
            "headers": request_headers,
            "params": request_params,
            "data": request_data,
            "json": request_json,
            "cookies": request_cookies,
        }

        request_kwargs = {"timeout": timeout, **request_context, **kwargs}

        request_context["kwargs"] = kwargs

        try:
            raw_response = await self._request(request_kwargs)
        except Exception as e:
            logger.bind(json=True).error(
                {
                    "Trigger": f"Third-{self.name}",
                    "request_context": request_context,
                    "request_error": repr(e),
                    "raw_response": None,
                },
            )
            return response_cls(
                success=False,
                data=None,
                code=ResponseCodeEnum.failed.value,
                message=f"Request to {request_kwargs['url']} Failed with {repr(e)}",
                request_context=request_context,
            )
        else:
            # try:
            #     response = raw_response.json()
            # except Exception:
            #     response = raw_response.text

            # logger.bind(json=True).debug(
            #     {
            #         "Trigger": f"Third-{self.name}",
            #         "request_context": request_context,
            #         "response": response,
            #     },
            # )

            return self.parse_response(
                request_context,
                raw_response,
                response_cls,
            )

    def parse_response(
        self,
        request_context: dict,
        raw_response: RawResponseType,
        response_cls: ResponseClsType,
    ) -> Response[Any]:
        return response_cls.parse_response(raw_response, request_context)


async def fetch(
    client: httpx.AsyncClient,
    response_cls: type[Response],
    method: str,
    url: str,
    params: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
    headers: dict | None = None,
) -> Response:
    """指定session/client request,  用于并发请求"""

    request_context = {
        "url": url,
        "params": params,
        "data": data,
        "json": json,
        "headers": headers,
    }
    try:
        raw_response = await client.request(
            method=method,
            url=url,
            params=params,
            data=data,
            json=json,
            headers=headers,
        )
    except Exception as e:
        return response_cls(
            success=False,
            data=None,
            code=ResponseCodeEnum.failed.value,
            message=f"Request to {url} Failed with {repr(e)}",
            request_context=request_context,
        )
    else:
        return response_cls.parse_response(raw_response, request_context)


async def multi_fetch(
    request_map: dict[str, tuple[type[Response], dict[str, Any]]],
) -> dict[str, Response]:
    """批量请求

    Args:
        request_map (dict[str, tuple[type[Response], dict]]):
        value[0] 为 response_cls
        value[1] 为
            {
                "method": "GET",
                "url": url,
                "params": params,
                "data": data,
                "json": json,
                "headers": headers,
            }

    Returns:
        dict[str, Response]: _description_
    """
    results = {}

    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=100),
        timeout=httpx.Timeout(None),
    ) as client:
        # Prepare tasks
        tasks = [
            fetch(
                client=client,
                response_cls=response_cls,
                **request_d,
            )
            for response_cls, request_d in request_map.values()
        ]

        # Execute tasks concurrently
        responses = await asyncio.gather(*tasks)

    # Store results in the dictionary
    for key, response in zip(request_map.keys(), responses, strict=True):
        results[key] = response

    return results


def test() -> None:
    class GoogleAPI(Third):
        @abc.abstractmethod
        async def search(self, *args, **kwargs) -> DefaultResponse[str]:
            pass

    google_apis = [
        API(
            "search",
            method="GET",
            uri="/search",
            response_cls=DefaultResponse[str],
        ),
    ]
    google_api = GoogleAPI(  # type: ignore
        name="GoogleAPI",
        protocol="https",
        host="www.google.com",
        port=None,
        response_cls=DefaultResponse[str],
        timeout=6,
        # headers={"auth": ":"},
    )
    for api in google_apis:
        google_api.register_api(api)

    print(await_in_sync(google_api.search(params={"q": "test"})))


if __name__ == "__main__":
    test()
