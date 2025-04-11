import sys
import inspect

from common.enums import *
from common.types import IntEnumMore, StrEnumMore


class StatusEnum(StrEnumMore):
    """启用状态"""

    enable = ("enable", "启用")
    disable = ("disable", "禁用")


class PermissionTypeEnum(StrEnumMore):
    """权限类型"""

    api = ("api", "API")


class SystemResourceTypeEnum(StrEnumMore):
    """系统资源类型"""

    menu = ("menu", "菜单")
    button = ("button", "按钮")
    api = ("api", "接口")


class SystemResourceSubTypeEnum(StrEnumMore):
    """系统资源子类型"""

    add_tab = ("add_tab", "选项卡")
    dialog = ("dialog", "弹窗")
    ajax = ("ajax", "Ajax请求")
    link = ("link", "链接")


class SendCodeScene(StrEnumMore):
    """发送短信场景"""

    login = ("login", "登录")
    reset_password = ("reset_password", "重置密码")
    change_account_phone = ("change_account_phone", "修改账户手机号")


class RespFormatEnum(StrEnumMore):
    """响应格式"""

    list_ = ("list", "列表")
    json_ = ("json", "JSON")


__enum_set__ = list(
    filter(
        lambda cls_name_and_cls: bool(
            issubclass(cls_name_and_cls[1], StrEnumMore | IntEnumMore)
            and cls_name_and_cls[1] not in [StrEnumMore, IntEnumMore],
        ),
        inspect.getmembers(sys.modules[__name__], inspect.isclass),
    ),
)


__enum_choices__ = [
    (
        cls_name_and_cls[0],
        cls_name_and_cls[1].__doc__.strip(),  # type: ignore
    )
    for cls_name_and_cls in __enum_set__
]


def get_enum_content(
    enum_name: str | None = None,
    is_reversed: bool = False,
) -> dict:
    enum_content = {}
    enum_list = []
    if enum_name:
        try:
            enum_cls = getattr(sys.modules[__name__], enum_name)
            enum_list.append((enum_name, enum_cls))
        except (AttributeError, NotImplementedError):
            pass
    else:
        enum_list = __enum_set__

    for name, cls in enum_list:
        # if format_ == EnumInfoResponseFormats.list_.value:
        #     enum_content[name] = cls.choices
        # else:
        if is_reversed:
            enum_content[name] = {v: k for k, v in cls._dict.items()}
        else:
            enum_content[name] = cls._dict

    return enum_content
