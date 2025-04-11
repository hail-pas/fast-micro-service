from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `knowledgefile` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_at` DATETIME(6) NOT NULL COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `deleted_at` BIGINT COMMENT '删除时间',
    `filename` VARCHAR(255) NOT NULL COMMENT '文件名',
    `ext` VARCHAR(10) NOT NULL COMMENT '文件扩展名',
    `size` INT NOT NULL COMMENT '文件大小',
    `url` VARCHAR(255) NOT NULL COMMENT '文件存储地址',
    `file_type` VARCHAR(50) NOT NULL COMMENT '文件类型',
    `info_id` INT NOT NULL COMMENT '知识库ID',
    KEY `idx_knowledgefi_created_07e530` (`created_at`),
    KEY `idx_knowledgefi_deleted_1845ec` (`deleted_at`)
) CHARACTER SET utf8mb4 COMMENT='文件表';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
