import uuid
from typing import TypeVar

from tortoise import fields, manager
from tortoise.models import Model
from tortoise.queryset import QuerySet
from tortoise.backends.base.client import BaseDBAsyncClient

from common.utils import datetime_now, sequential_uuid_from_ulid
from storages.relational.base.fields import TimestampField, BinaryUUIDField


class NotDeletedManager(manager.Manager):
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(deleted_at=0)


class UUIDPrimaryKeyModel(Model):
    id = BinaryUUIDField(
        description="主键",
        pk=True,
        default=sequential_uuid_from_ulid,
    )

    class Meta:
        abstract = True


class BigIntegerIDPrimaryKeyModel(Model):
    id = fields.BigIntField(description="主键", pk=True)

    class Meta:
        abstract = True


class TimeStampModel(Model):
    created_at = fields.DatetimeField(
        auto_now_add=True,
        description="创建时间",
        index=True,
    )
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
    deleted_at = TimestampField(
        index=True,
        description="删除时间",
    )

    all_objects = manager.Manager()

    class Meta:
        abstract = True

    async def save(
        self,
        using_db: BaseDBAsyncClient | None = None,
        update_fields: list[str] | None = None,  # type: ignore
        force_create: bool = False,
        force_update: bool = False,
    ) -> None:
        if update_fields:
            update_fields.append("updated_at")
        await super().save(using_db, update_fields, force_create, force_update)

    async def real_delete(
        self,
        using_db: BaseDBAsyncClient | None = None,
    ) -> None:
        await super().delete(using_db)

    async def delete(
        self,
        using_db: BaseDBAsyncClient | None = None,
    ) -> None:
        """fake delete"""
        self.deleted_at = datetime_now()
        await self.save(
            using_db=using_db,
            update_fields=["deleted_at"],
            force_update=True,
        )

    @classmethod
    async def delete_by_ids(cls, ids: list[int | str | uuid.UUID]) -> int:
        """batch fake delete"""
        return await cls.filter(id__in=ids).update(deleted_at=datetime_now(), updated_at=datetime_now())


BaseModelType = TypeVar("BaseModelType", bound="BaseModel")


class BaseModel(BigIntegerIDPrimaryKeyModel, TimeStampModel):
    class Meta:
        abstract = True


class CreateOnlyModel(Model):
    created_at = fields.DatetimeField(
        auto_now_add=True,
        description="创建时间",
        index=True,
    )

    class Meta:
        abstract = True
