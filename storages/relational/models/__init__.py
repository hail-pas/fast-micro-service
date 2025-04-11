from tortoise import Tortoise

from configs.defines import ConnectionNameEnum

Tortoise.init_models(
    [
        "storages.relational.models.user_center",
    ],
    ConnectionNameEnum.user_center.value,
)

Tortoise.init_models(
    [
        "storages.relational.models.knowledge_base",
    ],
    ConnectionNameEnum.knowledge_base.value,
)
