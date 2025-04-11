from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `resource` RENAME COLUMN `icon` TO `icon_path`;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `resource` RENAME COLUMN `icon_path` TO `icon`;"""
