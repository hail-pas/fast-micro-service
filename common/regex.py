import re
import socket
import string
import ipaddress

from _socket import gaierror

PHONE_REGEX_CN = re.compile(r"^1[3-9]\d{9}$")

PHONE_REGEX_GLOBAL = re.compile(r"^\+[1-9]\d{1,14}$")

EMAIL_REGEX = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")

LETTER_DIGITS_ONLY_REGEX = re.compile(r"^[a-zA-Z0-9]+$")

ACCOUNT_USERNAME_REGEX = re.compile(r"^(?!\d+$)[a-zA-Z0-9]{4,20}$")  # 不能是纯数字

LICENSE_NO_REGEX = re.compile(
    r"^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-HJ-NP-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂学警港澳]$",
)

URI_REGEX = re.compile(r"http[s]?://[^/]+(/[^?#]+)?")

PASSWORD_REGEX = re.compile(
    r"(?!^[0-9A-Z]+$)"
    r"(?!^[0-9a-z]+$)"
    r"(?!^[0-9!@#$%^&*()\":<>,.';~\-?/·]+$)"
    r"(?!^[A-Za-z]+$)"
    r"(?!^[A-Z!@#$%^&*()\":<>,.';~\-?/·]+$)"
    r"(?!^[a-z!@#$%^&*()\":<>,.';~\-?/·]+$)"
    r"(^[A-Za-z0-9!@#$%^&*()\":<>,.';~\-?/·]{8,20}$)",
)


def only_alphabetic_numeric(value: str) -> bool:
    if value is None:
        return False
    options = string.ascii_letters + string.digits + "_"
    if not all(i in options for i in value):
        return False
    return True


def validate_ip_or_host(value: int | str) -> tuple[bool, str]:
    try:
        return True, str(ipaddress.ip_address(value))
    except ValueError:
        if isinstance(value, int):
            return False, "不支持数字IP - {value}"
        try:
            socket.gethostbyname(value)
            return True, value
        except gaierror as e:
            return False, f"获取HOST{value}失败: {e}"
