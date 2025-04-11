# ruff: noqa
from enum import IntEnum, StrEnum, EnumMeta
from typing import Annotated

from pydantic import SecretStr
from pydantic.functional_validators import AfterValidator, BeforeValidator


class MyEnumMeta(EnumMeta):
    def __call__(cls, value, label: str = ""):  # type: ignore
        obj = super().__call__(value)  # type: ignore
        obj._value_ = value
        if label:
            obj._label = label
        else:
            obj._label = obj._dict[value]
        return obj

    def __new__(metacls, cls, bases, classdict):  # type: ignore
        enum_class = super().__new__(metacls, cls, bases, classdict)
        enum_class._dict = {member.value: member.label for member in enum_class}  # type: ignore
        enum_class._help_text = ", ".join([f"{member.value}: {member.label}" for member in enum_class])  # type: ignore
        return enum_class


class StrEnumMore(StrEnum, metaclass=MyEnumMeta):
    _dict: dict[str, str]
    _help_text: str

    def __new__(cls, value, label: str = ""):  # type: ignore
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._label = label  # type: ignore
        return obj

    @property
    def label(self):
        """The value of the Enum member."""
        return self._label  # type: ignore


class IntEnumMore(IntEnum, metaclass=MyEnumMeta):
    _dict: dict[int, str]
    _help_text: str

    def __new__(cls, value, label: str = ""):  # type: ignore
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj._label = label  # type: ignore
        return obj

    @property
    def label(self):
        """The value of the Enum member."""
        return self._label  # type: ignore


# datetime = Annotated[
#     origin_datetime,
#     PlainSerializer(lambda _datetime: _datetime.strftime("%Y-%m-%d %H:%M:%S"), return_type=origin_datetime),
# ]


RoundFloat = Annotated[
    float,
    BeforeValidator(lambda x: round(x, 2)),
    # PlainSerializer(
    #     lambda x: round(x, 2),
    #     return_type=float,
    # )
]


class SecretEmail(SecretStr):
    """yy****@xxx.com隐藏第2至@位"""

    def _display(self) -> str:
        # return f"{self.get_secret_value()[:4]}******{self.get_secret_value()[8:]}"
        v = self.get_secret_value()
        _index = v.index("@")
        return f"{self.get_secret_value()[:1]}******{self.get_secret_value()[_index:]}"


class SecretPhone(SecretStr):
    """手机号隐藏第4至8位"""

    def _display(self) -> str:
        return f"{self.get_secret_value()[:3]}****{self.get_secret_value()[7:]}"


ValidStringOrNone = Annotated[str | None, AfterValidator(lambda v: None if not v else v)]
