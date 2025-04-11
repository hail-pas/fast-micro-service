# ruff: noqa: RET504
from math import ceil
from typing import Self, Generic, TypeVar
from datetime import datetime
from collections.abc import Sequence

import orjson
from pydantic import Field, BaseModel, ValidationInfo, field_validator, model_validator
from fastapi.responses import ORJSONResponse
from starlette_context import context

from common.enums import ResponseCodeEnum
from common.utils import datetime_now
from common.context import ContextKeyEnum
from common.schemas import Pager, CRUDPager
from common.pydantic import CommonConfigDict


class AesResponse(ORJSONResponse):
    def render(self, content: dict) -> bytes:
        """AES加密响应体"""
        # if not get_settings().DEBUG:
        # content = AESUtil(local_configs.AES.SECRET).encrypt_data(
        #       orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS).decode())
        if isinstance(content, str):
            dump_content = content.encode()

        else:
            dump_content = orjson.dumps(
                content,
                option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_PASSTHROUGH_DATETIME,
            )

        return dump_content


DataT = TypeVar("DataT")


# def validate_trace_id(v: str, info: ValidationInfo) -> str:
#     if not v:
#         v = str(context.get(ContextKeyEnum.request_id.value, ""))
#     return v


# TraceId = Annotated[str, PlainValidator(validate_trace_id)]


class Resp(BaseModel, Generic[DataT]):
    """响应Model."""

    model_config = CommonConfigDict

    code: int = Field(
        default=ResponseCodeEnum.success,
        description=f"业务响应代码, {ResponseCodeEnum._dict}",  # type: ignore
    )
    response_time: datetime | None = Field(
        default_factory=datetime_now,
        description="响应时间",
    )
    message: str | None = Field(default=None, description="响应提示信息")
    data: DataT | None = Field(
        default=None,
        description="响应数据格式",
    )
    trace_id: str = Field(default="", description="请求唯一标识", validate_default=True)

    @field_validator("trace_id")
    @classmethod
    def set_trace_id(cls, value: str, info: ValidationInfo) -> str:
        if not value:
            value = str(context.get(ContextKeyEnum.request_id.value, ""))
        return value

    @model_validator(mode="after")
    def set_failed_response(self) -> Self:
        context[ContextKeyEnum.response_code.value] = self.code
        if self.code != ResponseCodeEnum.success:
            context[ContextKeyEnum.response_data.value] = {
                "code": self.code,
                "message": self.message,
                "data": self.data,
            }
        return self

    @classmethod
    def fail(
        cls,
        message: str,
        code: int = ResponseCodeEnum.failed.value,
    ) -> Self:
        return cls(code=code, message=message)


class PyTestResp(Resp):
    # PyTestResp类继承自Resp类，用于pytest测试响应
    @model_validator(mode="after")
    def set_failed_response(self) -> Self:
        """没有用到fastapi的context, 重写使用时防止报错"""
        return self


class SimpleSuccess(Resp):
    """简单响应成功."""


class PageInfo(BaseModel):
    """翻页相关信息."""

    total_page: int
    total_count: int
    size: int
    page: int


class PageData(BaseModel, Generic[DataT]):
    page_info: PageInfo
    records: Sequence[DataT]

    def __init__(
        self,
        records: Sequence[DataT],
        total_count: int = 0,
        pager: Pager | CRUDPager = None,
        page_info: PageInfo | None = None,
    ) -> None:
        if page_info is None:
            page_info = generate_page_info(total_count, pager)
        super().__init__(
            page_info=page_info,
            records=records,
        )


def generate_page_info(total_count: int, pager: Pager | CRUDPager) -> PageInfo:
    return PageInfo(
        total_page=ceil(total_count / pager.limit),
        total_count=total_count,
        size=pager.limit,
        page=pager.offset // pager.limit + 1,
    )
