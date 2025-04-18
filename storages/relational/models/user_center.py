from typing import Self

from tortoise import fields, models

from storages import enums
from common.regex import EMAIL_REGEX, PHONE_REGEX_CN, ACCOUNT_USERNAME_REGEX
from common.utils import datetime_now
from storages.oss import OssProxy
from configs.config import local_configs
from configs.defines import ConnectionNameEnum
from storages.aredis.keys import UserCenterKey
from storages.relational.base.fields import FileField
from storages.relational.base.models import (
    BaseModel,
    CreateOnlyModel,
    NotDeletedManager,
    BigIntegerIDPrimaryKeyModel,
)
from storages.relational.base.validators import RegexValidator, MinLengthValidator

UserCenterConnection = ConnectionNameEnum.user_center.value


class Account(BaseModel):
    """用户
    Redis 实时缓存用户基本信息和权限码
    """

    username = fields.CharField(
        max_length=20,
        description="用户名",
        validators=[
            MinLengthValidator(
                min_length=4,
                error_message_template="长度需要 >= 4",
                default_ctx={"field_name": "用户名"},
            ),
            RegexValidator(
                ACCOUNT_USERNAME_REGEX.pattern,
                0,
                default_ctx={
                    "field_name": "用户名",
                },
                error_message_template="只能输入字母和数字的组合",
            ),
        ],
    )
    phone = fields.CharField(
        validators=[
            RegexValidator(
                PHONE_REGEX_CN.pattern,
                0,
                default_ctx={"field_name": "手机号"},
            ),
        ],
        max_length=11,
        description="手机号",
    )
    email = fields.CharField(
        max_length=50,
        description="邮箱",
        null=True,
        validators=[
            RegexValidator(
                EMAIL_REGEX.pattern,
                0,
                default_ctx={"field_name": "邮箱"},
            ),
        ],
    )
    # real_name = fields.CharField(max_length=64, description="姓名")
    is_staff = fields.BooleanField(default=False, description="是否是后台管理员")
    is_super_admin = fields.BooleanField(
        default=False,
        description="是否是后台超级管理员",
    )
    status = fields.CharEnumField(
        max_length=16,
        enum_type=enums.StatusEnum,
        description="状态",
        default=enums.StatusEnum.enable,
    )
    last_login_at = fields.DatetimeField(null=True, description="最近一次登录时间")
    remark = fields.CharField(max_length=200, description="备注", default="")
    # 密码加密存储
    password = fields.CharField(max_length=255, description="密码")
    role: fields.ForeignKeyRelation["Role"] = fields.ForeignKeyField(
        f"{UserCenterConnection}.Role",
        related_name="accounts",
        description="角色",
    )

    def __str__(self) -> str:
        return self.username

    def status_display(self) -> str:
        """状态显示"""
        return enums.StatusEnum._dict.get(self.status, "")

    def days_from_last_login(self) -> int | None:
        """距上一次登录天数

        Returns:
            int | None: 从未登录的情况为None
        """
        if not self.last_login_at:
            return None
        return (datetime_now() - self.last_login_at).days

    async def has_permission(
        self,
        apis: list[str],
        conn_name: ConnectionNameEnum = ConnectionNameEnum.user_center,
    ) -> bool:
        # OR
        async with local_configs.redis.get_redis(service=conn_name) as _redis:
            result = await _redis.smismember(
                name=UserCenterKey.AccountApiPermissionSet.format(uuid=str(self.id)),  # type: ignore
                values=apis,
            )
        if 1 in result:
            return True
        return False

    async def update_cache_permissions(
        self,
        conn_name: ConnectionNameEnum = ConnectionNameEnum.user_center,
    ) -> None:
        perms = await self.get_permission_codes()
        async with local_configs.redis.get_redis(conn_name) as r:
            async with r.pipeline() as pipe:
                pipe.delete(UserCenterKey.AccountApiPermissionSet.format(uuid=str(self.id)))
                if perms:
                    # 刷新接口权限
                    pipe.sadd(
                        UserCenterKey.AccountApiPermissionSet.format(uuid=str(self.id)),  # type: ignore
                        *perms,  # type: ignore
                    )
                await pipe.execute()

    async def get_permission_codes(self) -> list[str]:
        """获取用户的全部permission codes

        Args:
            account (Account): _description_

        Returns:
            list[str]: _description_
        """
        permission_codes: list[str] = []
        if self.is_super_admin:
            return ["*"]
        resource_ids = await self.get_account_resource_ids()  # type: ignore
        if not resource_ids:
            return permission_codes
        return await Permission.filter(  # type: ignore
            resources__id__in=resource_ids,
        ).values_list("code", flat=True)

    async def get_account_resource_ids(
        self,
    ) -> list[str]:
        _args = []
        _kwargs = {
            "enabled": True,
            "assignable": True,
        }
        if self.is_staff:
            _kwargs = {
                "enabled": True,
            }
        if self.is_super_admin:
            return await Resource.filter(*_args, **_kwargs).values_list("id", flat=True)  # type: ignore
        _kwargs["roles__id"] = self.role_id  # type: ignore
        return await Resource.filter(*_args, **_kwargs).values_list("id", flat=True)  # type: ignore

    @classmethod
    async def get_by_identifier(cls, identifier: str) -> Self | None:
        filter_ = {}
        if PHONE_REGEX_CN.match(identifier):
            filter_["phone"] = identifier
        elif EMAIL_REGEX.match(identifier):
            filter_["email"] = identifier
        elif ACCOUNT_USERNAME_REGEX.match(identifier):
            filter_["username"] = identifier
        else:
            return None

        return await cls.filter(**filter_, deleted_at=0).first()

    class Meta:
        table_description = "用户"
        app = UserCenterConnection
        ordering = ["-id"]
        unique_together = (
            ("username", "deleted_at"),
            ("phone", "deleted_at"),
            ("email", "deleted_at"),
        )
        manager = NotDeletedManager()
        unique_error_messages = {
            "account.uid_account_username_4f1849": "用户名已存在",
            "account.uid_account_phone_9b9e7e": "手机号已存在",
            "account.uid_account_email_a28fc7": "邮箱地址已存在",
        }


class Role(BaseModel):
    label = fields.CharField(max_length=50, description="名称")
    remark = fields.CharField(max_length=200, description="备注", null=True)

    # reversed relations
    accounts: fields.ReverseRelation[Account]
    resources: fields.ManyToManyRelation["Resource"]

    class Meta:
        table_description = "角色"
        ordering = ["-id"]
        app = UserCenterConnection
        unique_together = (("label", "deleted_at"),)


class Permission(models.Model):
    code = fields.CharField(pk=True, max_length=256, description="权限码")
    label = fields.CharField(max_length=128, description="权限名称")
    permission_type = fields.CharEnumField(
        max_length=16,
        enum_type=enums.PermissionTypeEnum,
        description=f"权限类型, {enums.PermissionTypeEnum._help_text}",
        default=enums.PermissionTypeEnum.api,
    )
    is_deprecated = fields.BooleanField(default=False, description="是否废弃")
    # reversed relations
    resources: fields.ManyToManyRelation["Resource"]

    class Meta:
        table_description = "权限"
        ordering = ["-code"]
        app = UserCenterConnection


class Resource(BigIntegerIDPrimaryKeyModel, CreateOnlyModel):
    code = fields.CharField(
        max_length=32,
        description="资源编码{parent}:{current}",
        index=True,
    )
    icon_path = FileField(
        max_length=256,
        description="图标",
        null=True,
        storage=OssProxy.client(),
    )
    label = fields.CharField(max_length=64, description="资源名称", index=True)
    front_route = fields.CharField(
        max_length=128,
        description="前端路由",
        null=True,
        blank=True,
    )
    resource_type = fields.CharEnumField(
        max_length=16,
        enum_type=enums.SystemResourceTypeEnum,
        description=f"资源类型, {enums.SystemResourceTypeEnum._help_text}",
    )
    sub_resource_type = fields.CharEnumField(
        max_length=16,
        enum_type=enums.SystemResourceSubTypeEnum,
        description=f"资源类型, {enums.SystemResourceSubTypeEnum._help_text}",
    )
    order_num = fields.IntField(default=1, description="排列序号")
    enabled = fields.BooleanField(default=True, description="是否可用")
    assignable = fields.BooleanField(default=True, description="是否可分配")
    parent = fields.ForeignKeyField(  # type: ignore
        model_name=f"{UserCenterConnection}.Resource",
        related_name="children",
        null=True,
        description="父级",
    )
    scene = fields.CharEnumField(enum_type=enums.TokenSceneTypeEnum, max_length=16, description="场景")
    permissions: fields.ManyToManyRelation[Permission] = fields.ManyToManyField(
        model_name=f"{UserCenterConnection}.Permission",
        related_name="resources",
    )
    roles: fields.ManyToManyRelation["Role"] = fields.ManyToManyField(
        model_name=f"{UserCenterConnection}.Role",
        related_name="resources",
    )

    # reversed relations
    children: fields.ReverseRelation["Resource"]

    def type_display(self) -> str:
        """类型显示"""
        return self.resource_type.label

    def sub_type_display(self) -> str | None:
        """子类型显示"""
        return self.sub_resource_type.label

    def scene_display(self) -> str:
        return self.scene.label

    class Meta:
        table_description = "系统资源"
        ordering = ["order_num"]
        unique_together = (("code", "parent", "scene"),)
        app = UserCenterConnection


class Config(models.Model):
    key = fields.CharField(max_length=128, description="配置项key", unique=True)
    value = fields.JSONField(default=dict, description="配置项值")
    description = fields.CharField(max_length=255, description="配置项描述")

    class Meta:
        table_description = "系统配置"
        ordering = ["-id"]
        app = UserCenterConnection


# class OSSFile(models.Model):
#     """
#     用于存储OSS文件路径
#     ---
#     """

#     # oss_file_path : ("table_name", "field_name", "file_name   ")
#     oss_file_path = fields.CharField(max_length=255, description="OSS文件路径", unique=True)
#     created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
#     db_connection = fields.CharField(max_length=32, description="数据库连接名称")

#     class Meta:
#         table_description = "OSS文件"
#         ordering = ["-id"]
#         app = _app

#     @classmethod
#     async def create_oss_file(cls, oss_file_path: str) -> Self:
#         """
#         创建OSS文件
#         ---
#         """
#         return await cls.create(oss_file_path=oss_file_path)

#     @classmethod
#     async def delete_oss_file(cls, oss_file_path: str) -> None:
#         """
#         删除OSS文件
#         ---
#         """
#         await cls.filter(oss_file_path=oss_file_path).delete()

#     @classmethod
#     async def clear_oss_file(cls) -> None:
#         """
#         清理OSS文件
#         """
#         all_file = await cls.all().iterator()
#         from pypika import Query, Table

#         wait_delete_list = []
#         for ins in all_file:
#             table_name, field_name, file_name = ins.oss_file_path.split("/")
#             table = Table(table_name)
#             query = Query.from_(table).select(1).where(**{field_name: ins.oss_file_path})
#             res = connections.get(ins.db_connection).execute(str(query))
#             if res:
#                 continue
#             wait_delete_list.append(ins)
#         if wait_delete_list:
#             # 删除oss 文件
#             await cls.bulk_delete(wait_delete_list)


# ==============操作日志 =============
# class OperationRecord(UUIDPrimaryKeyModel, CreateOnlyModel):
#     account: fields.ForeignKeyRelation[Account] = fields.ForeignKeyField(
#         model_name=f"{_app}.Account",
#         related_name="operation_records",
#         description="操作账户",
#     )
#     item = fields.CharField(
#         max_length=128,
#         description="操作对象/操作类型",
#         index=True,
#     )
#     role_name = fields.CharField(max_length=255, description="角色名称", default="")
#     operation_time = fields.DatetimeField(
#         description="操作时间",
#         index=True,
#     )
#     description = fields.TextField(description="操作描述")
#     request_data = fields.JSONField(default=dict, description="请求json数据")
#     response_data = fields.JSONField(default=dict, description="响应json数据")
#     unique_id = fields.UUIDField(unique=True, description="唯一ID")

#     class Meta:
#         table_description = "操作记录"
#         ordering = ["-id"]
#         app = _app
