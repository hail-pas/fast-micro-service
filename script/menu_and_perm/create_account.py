import sys
import asyncio

sys.path.append(".")  # noqa

from common.encrypt import PasswordUtil

# from storages.enums import GenderEnum
from common.init_ctx import init_ctx  # noqa
from storages.relational.models.user_center import Role, Account, Resource  # noqa

accs = []


async def create_accounts(role):
    for acc in accs:
        print(f"创建账号：{acc}")
        acc.update({"role_id": role.id})
        user_name = acc.pop("username")
        await Account.update_or_create(defaults=acc, deleted_at=0, username=user_name)


async def init_superuser_role():
    role, _ = await Role.update_or_create(label="超级管理员")
    all_res = await Resource.all()
    await role.resources.add(*all_res)
    return role


async def main():
    await init_ctx()
    role = await init_superuser_role()
    await create_accounts(role=role)


def get_input(prompt, required=True, type_=str):
    while True:
        value = input(prompt)
        if value or not required:
            try:
                return type_(value)
            except ValueError:
                print("输入不符合要求，请重新输入。")
        else:
            print(f"{prompt}不能为空，请重新输入。")


if __name__ == "__main__":
    username = get_input("请输入用户名：", required=True, type_=str)
    phone = get_input("请输入手机号：", required=True, type_=str)
    password = get_input("请输入密码：", required=True, type_=str)
    real_name = get_input("请输入姓名：", required=True, type_=str)
    email = get_input("请输入邮箱(可选)：", required=False, type_=str)
    accs.append(
        {
            "real_name": real_name,
            "username": username,
            "email": email or None,
            "phone": phone,
            # "gender": GenderEnum(gender),
            "is_super_admin": True,
            "is_staff": True,
            "status": "enable",
            "password": PasswordUtil.get_password_hash(password),
        },
    )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
