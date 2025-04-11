from tortoise import Tortoise

from configs.config import local_configs
from common.monkey_patch import patch


async def init_ctx_relational() -> None:
    await Tortoise.init(config=local_configs.relational.tortoise_orm_config)


async def init_ctx() -> None:
    patch()
    await init_ctx_relational()
