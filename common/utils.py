import re
import uuid
import random
import socket
import string
import asyncio
import gettext
import datetime
import posixpath
from typing import Any, Union, Generic, Literal, TypeVar
from zoneinfo import ZoneInfo
from collections.abc import Callable, Hashable, Iterable, Coroutine

from ulid import ULID
from fastapi import FastAPI
from cachetools import LRUCache
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.requests import Request

from configs.config import local_configs

DATETIME_FORMAT_STRING = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT_STRING = "%Y-%m-%d"

PI = 3.1415926535897932384626  # π


def generate_random_string(
    length: int,
    all_digits: bool = False,
    excludes: list[str] | None = None,
) -> str:
    """生成任意长度字符串."""
    if excludes is None:
        excludes = []
    all_char = string.digits if all_digits else string.ascii_letters + string.digits
    if excludes:
        for char in excludes:
            all_char = all_char.replace(char, "")
    # return "".join(random.sample(all_char, length))
    return "".join(random.SystemRandom().choice(all_char) for _ in range(length))


def get_client_ip(request: Request) -> str | None:
    """获取客户端真实ip
    :param request:
    :return:
    """
    client_ip = None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",", 1)[0]
    if not client_ip and request.client:
        client_ip = request.client.host
    return client_ip


def datetime_now() -> datetime.datetime:
    # 返回带有时区信息的时间
    return datetime.datetime.now(
        tz=local_configs.relational.timezone,
    )


def commify(_n: Union[int, float]) -> str | None:
    """Add commas to an integer `n`.
    raise:
        TypeError: type check
    >>> commify(1)
    '1'
    >>> commify(123)
    '123'
    >>> commify(-123)
    '-123'
    >>> commify(1234)
    '1,234'
    >>> commify(1234567890)
    '1,234,567,890'
    >>> commify(123.0)
    '123.0'
    >>> commify(1234.5)
    '1,234.5'
    >>> commify(1234.56789)
    '1,234.56789'
    >>> commify(' %.2f ' % -1234.5)
    '-1,234.50'
    >>> commify(None)
    >>>.
    """
    if _n is None:
        return None

    if not isinstance(_n, (int, float)):
        raise TypeError("n must be an integer or float.")

    n = str(_n).strip()

    if n.startswith("-"):
        prefix = "-"
        n = n[1:].strip()
    else:
        prefix = ""

    if "." in n:
        dollars, cents = n.split(".")
    else:
        dollars, cents = n, None

    r = []  # type: ignore
    for i, c in enumerate(str(dollars)[::-1]):
        if i and (not (i % 3)):
            r.insert(0, ",")
        r.insert(0, c)
    out = "".join(r)
    if cents:
        out += "." + cents
    return prefix + out


def mapper(
    func: Callable[[list | dict | Any], list | dict | Any],
    ob: Union[list, dict],
) -> list | dict | Any:
    """Map func for list or dict."""
    if isinstance(ob, list):
        result = []
        for i in ob:
            result.append(mapper(func, i))
    elif isinstance(ob, dict):
        result = {}  # type: ignore
        for k, v in ob.items():
            value = mapper(func, v) if isinstance(v, (list, dict)) else func(v)
            result[k] = value
    else:
        return func(ob)
    return result


def seconds_to_format_str(
    seconds: int,
    format_str: str = DATETIME_FORMAT_STRING,
    offset: Union[float, int] = 1,
    tzinfo: ZoneInfo | None = None,
) -> str:
    """时间戳装换为对应格式化时间, 需要传秒级时间戳 或者 配合offset转换成秒级."""
    if not tzinfo:
        tzinfo = local_configs.relational.timezone
    v = datetime.datetime.fromtimestamp(seconds * offset, tz=tzinfo)
    return v.strftime(format_str)


def format_str_to_seconds(
    value: datetime.datetime | str,
    format_str: str = DATETIME_FORMAT_STRING,
    tzinfo: ZoneInfo | None = None,
) -> int:
    """格式化时间转换为对应时区的时间戳."""
    if not tzinfo:
        tzinfo = local_configs.relational.timezone
    if isinstance(value, datetime.datetime):
        value = value.replace(tzinfo=tzinfo)
    else:
        value = datetime.datetime.strptime(value, format_str).replace(
            tzinfo=tzinfo,
        )
    return int(value.timestamp())


def seconds_to_readable_display(
    seconds: int,
    display_language: Literal["en", "cn"] = "cn",
    level: Literal[1, 2, 3, 4] = 3,
) -> str:
    """将妙转换成human readable展示"""
    is_negative = False
    if seconds < 0:
        seconds = abs(seconds)
        is_negative = True
        # return "-"

    d = seconds // (60 * 60 * 24)
    seconds -= d * (60 * 60 * 24)
    s = seconds % 60
    seconds //= 60
    m = seconds % 60
    seconds //= 60
    h = seconds % 60
    result = []

    match display_language:
        case "cn":
            d_appendix = "天"
            h_appendix = "小时"
            m_appendix = "分钟"
            s_appendix = "秒"
        case "en":
            d_appendix = "d"
            h_appendix = "h"
            m_appendix = "m"
            s_appendix = "s"
        case _:
            d_appendix = "天"
            h_appendix = "小时"
            m_appendix = "分钟"
            s_appendix = "秒"

    result.append(f"{d}{d_appendix}" if d else "")
    result.append(f"{h}{h_appendix}" if h else "")
    result.append(f"{m}{m_appendix}" if m else "")
    result.append(f"{s}{s_appendix}" if s else "")

    result = result[:level]
    if is_negative:
        return "-" + "".join(result)
    return "".join(result)


def filter_dict(
    dict_obj: dict,
    callback: Callable[[Hashable, Any], bool],
) -> dict:
    """适用于字典的filter."""
    new_dict = {}
    for key, value in dict_obj.items():
        if callback(key, value):
            new_dict[key] = value
    return new_dict


def merge_dict(dict1: dict, dict2: dict) -> dict:
    # 遍历第二个字典，只有当键不存在于第一个字典中时，才更新第一个字典
    for key, value in dict2.items():
        dict1.setdefault(key, value)
    return dict1


def flatten_list(element: Iterable) -> list[Any]:
    """Iterable 递归展开成一级列表."""
    flat_list = []

    def _flatten_list(e: Any) -> None:
        if type(e) in [list, set, tuple]:
            for item in e:
                _flatten_list(item)
        else:
            flat_list.append(e)

    _flatten_list(element)

    return flat_list


def snake2camel(snake: str, start_lower: bool = False) -> str:
    """Converts a snake_case string to camelCase.
    The `start_lower` argument determines whether the first letter in the generated camelcase should
    be lowercase (if `start_lower` is True), or caPItalized (if `start_lower` is False).
    """
    camel = snake.title()
    camel = re.sub("([0-9A-Za-z])_(?=[0-9A-Z])", lambda m: m.group(1), camel)
    if start_lower:
        camel = re.sub("(^_*[A-Z])", lambda m: m.group(1).lower(), camel)
    return camel


def camel2snake(camel: str) -> str:
    """Converts a camelCase string to snake_case."""
    snake = re.sub(
        r"([a-zA-Z])([0-9])",
        lambda m: f"{m.group(1)}_{m.group(2)}",
        camel,
    )
    snake = re.sub(
        r"([a-z0-9])([A-Z])",
        lambda m: f"{m.group(1)}_{m.group(2)}",
        snake,
    )
    return snake.lower()


def await_in_sync(to_await: Coroutine) -> Any:  # ruff: noqa
    """
    同步环境执行异步
    """
    async_response = []

    async def run_and_capture_result() -> None:
        r = await to_await
        async_response.append(r)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    coroutine = run_and_capture_result()
    loop.run_until_complete(coroutine)
    return async_response[0]


def get_self_ip_address():
    """
    获取本机ip地址
    :return:
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]


def get_enum_field_display(self, field_name: str):
    """获取Model的Enum字段label

    Args:
        field_name (str): 字段名

    Returns:
        Any: 对应label
    """
    value = getattr(self, field_name)
    if value is None:
        return value
    return value._dict.get(value.value, value.value)  # type: ignore  # type: ignore


def gte_all_uris(
    app: FastAPI,
    _filter: Callable[[Route | WebSocketRoute | Mount], bool] | None = None,
) -> list[dict[str, Any]]:
    """获取app下所有的URI

    Args:
        app (FastAPI): FastAPI App

    Returns:
        list[str]: URI 列表
    """
    uri_list = []
    paths = []

    def get_uri_list(_app: FastAPI | Mount, prefix: str = ""):
        for route in _app.routes:
            route_info = {
                "path": f"{prefix}{route.path}",  # type: ignore
                "name": getattr(route, "summary", None) or route.name,  # type: ignore
                "tags": getattr(route, "tags", []),
                "operation_id": getattr(route, "operation_id", None),  # type: ignore
            }
            if _filter and not _filter(route):  # type: ignore
                continue
            if isinstance(route, Route):
                if not route.methods:
                    continue
                for method in route.methods:
                    full_path = f"{method}:{route_info['path']}"
                    if method in ["HEAD", "OPTIONS"] or full_path in paths:
                        continue
                    uri_list.append(
                        {
                            "method": method,
                            **route_info,
                        },
                    )
                    paths.append(full_path)
            elif isinstance(route, WebSocketRoute):
                if f"{method}:{route_info['path']}" in paths:
                    continue
                uri_list.append(
                    {
                        "method": "ws",
                        **route_info,
                    },
                )
                paths.append(full_path)
            elif isinstance(route, Mount):
                get_uri_list(route, prefix=f"{prefix}{route.path}")

    get_uri_list(app)
    return uri_list


def swap_uuid_sections(uuid_obj: uuid.UUID, recovery: bool = False) -> bytes:
    """将时间戳和变体号交换, 使其单向递增. 仅对uuid1有效

    123e4567-e89b-12d3-a456-42661417400
    一个UUID包含了几个部分的信息:
        4个字节:时间戳信息
        2个字节:版本号
        2个字节:变体号
        6个字节:唯一性标识符(MAC地址和进程ID等生成)

    不同字节部分对应UUID的不同信息:
        第一个4字节(12 3e 45 67)是时间戳信息
        接下来2字节(e8 9b)是版本号
        再下来2字节(12 d3)是变体号
        最后6字节(a4 56 42 66 14 17 40 00)是唯一性标识符
    """
    uuid_bytes = uuid_obj.bytes
    if recovery:
        swapped_uuid_bytes = uuid_bytes[4:8] + uuid_bytes[2:4] + uuid_bytes[:2] + uuid_bytes[8:]
    else:
        swapped_uuid_bytes = uuid_bytes[6:8] + uuid_bytes[4:6] + uuid_bytes[:4] + uuid_bytes[8:]
    return swapped_uuid_bytes


def uuid_to_bin(uuid_obj: uuid.UUID, swap_flag: Literal[0, 1] = 1) -> bytes:
    if swap_flag == 1:
        uuid_bytes = swap_uuid_sections(uuid_obj)
    else:
        uuid_bytes = uuid_obj.bytes
    return uuid_bytes


def bin_to_uuid(uuid_bytes: bytes, swap_flag: Literal[0, 1] = 1) -> uuid.UUID:
    uuid_obj = uuid.UUID(bytes=uuid_bytes)
    if swap_flag == 1:
        uuid_bytes = swap_uuid_sections(uuid_obj, recovery=True)
    return uuid.UUID(bytes=uuid_bytes)


def sequential_uuid_from_ulid() -> uuid.UUID:
    # return uuid.UUID(bytes=uuid_to_bin(uuid.uuid1()))
    return ULID().to_uuid()  # type: ignore


def normalize_url(url: str) -> str:
    if not url.startswith("http://") and not url.startswith(
        "https://",
    ):  # noqa
        return "https://" + url
    return url


def clean_path(name: str) -> str:
    """
    Cleans the path so that Windows style paths work
    """
    # Normalize Windows style paths
    clean_name = posixpath.normpath(name).replace("\\", "/")

    # os.path.normpath() can strip trailing slashes so we implement
    # a workaround here.
    if name.endswith("/") and not clean_name.endswith("/"):
        # Add a trailing slash as it was stripped.
        return clean_name + "/"
    return clean_name


def count_left_shifts_from_one(number: int) -> int:
    if number < 1:
        raise ValueError("Number must be greater than 1.")

    shifts = 0

    # 执行右移操作直到数值变为1
    while number > 1:
        number >>= 1
        shifts += 1
    return shifts


T = TypeVar("T")


class PersistentCache(Generic[T]):
    def __init__(self, max_size: int):
        self.cache: LRUCache = LRUCache(maxsize=max_size)
        self.lock = asyncio.Lock()  # 创建锁

    async def get(self, key: str) -> T:
        async with self.lock:  # 确保线程安全
            return self.cache.get(key)

    async def set(self, key: str, value: T):
        async with self.lock:  # 确保线程安全
            self.cache[key] = value


class Translator:
    _instances: dict[str, "Translator"] = {}
    _translations: dict[str, gettext.GNUTranslations] = {}

    def __new__(cls, lang: str) -> "Translator":
        if lang not in cls._instances:
            cls._instances[lang] = super(Translator, cls).__new__(cls)
        return cls._instances[lang]

    def __init__(self, lang: Literal["zh", "en"]):
        self.lang = lang

    def load_translations(self, key: str) -> gettext.GNUTranslations:
        cache_key = f"{self.lang}:{key}"
        if cache_key in self._translations:
            return self._translations[cache_key]

        # Load translations from file
        translation = gettext.translation(key, localedir="locales", languages=[self.lang])
        self._translations[cache_key] = translation
        return translation

    def t(self, key: str, message: str, **kwargs: dict[str, Any]) -> str:
        translated_message = self.load_translations(key).gettext(message)
        return translated_message.format(**kwargs)
