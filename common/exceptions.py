from common.responses import ResponseCodeEnum


class ApiException(Exception):
    """非 0 的业务错误."""

    code: int = ResponseCodeEnum.failed.value
    message: str

    def __init__(
        self,
        message: str,
        code: int = ResponseCodeEnum.failed.value,
    ) -> None:
        self.code = code
        self.message = message


class ValidationError(Exception):
    """自定义校验异常
    1. 覆盖tortoise Validation Error, 用于自定义提示语
    """

    error_type: str
    error_message_template: str
    ctx: dict  # value

    def __init__(
        self,
        error_type: str,
        error_message_template: str,
        ctx: dict,
    ) -> None:
        self.error_type = error_type
        self.error_message_template = error_message_template
        self.ctx = ctx

    def __str__(self) -> str:
        msg = self.error_message_template.format(**self.ctx)
        field_name = self.ctx.get("field_name")
        if field_name:
            msg = f"{field_name}: {msg}"
        return msg
