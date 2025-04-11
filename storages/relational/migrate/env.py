from configs.config import local_configs

TORTOISE_ORM_CONFIG = local_configs.relational.tortoise_orm_config

# 写配置块 [tool.aerich] 到 pyproject.toml
# aerich init -t storages.relational.migrate.env.TORTOISE_ORM_CONFIG --location storages/relational/migrate
# 初始化迁移目录和记录表
# aerich --app {app} init-db
# aerich --app {app} migrate
# aerich --app {app} upgrade
