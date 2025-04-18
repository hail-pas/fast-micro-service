from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from aerich import Command
from fastapi import FastAPI
from tortoise import Tortoise

from common.service_api import ServiceApi
from configs.config import local_configs
from configs.defines import VersionFilePath, ConnectionNameEnum
from apis.middlewares import roster as middleware_roster
from service.exceptions import roster as exception_handler_roster
from apis.knowledge_base.v1 import router as v1_router
from apis.knowledge_base.v2 import router as v2_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # 初始化及退出清理

    # tortoise
    await Tortoise.init(config=app.settings.relational.tortoise_orm_config)

    # pre-check
    for connection in ConnectionNameEnum:
        await Tortoise.get_connection(connection.value).execute_query("SELECT 1")

    yield

    await Tortoise.close_connections()


class KnowledgeBaseServiceApi(ServiceApi):
    async def before_server_start(self) -> None:
        command = Command(
            tortoise_config=self.settings.relational.tortoise_orm_config,
            app=ConnectionNameEnum.knowledge_base.value,
            location=VersionFilePath,
        )
        await command.init()
        await command.upgrade(run_in_transaction=True)


knowledge_base_api = KnowledgeBaseServiceApi(
    code=local_configs.project.unique_code.knowledge_base,
    settings=local_configs,
    title="知识库中心",
    description="统一知识库管理中心",
    lifespan=lifespan,
    version="1.0.0",
    redirection_url="/docs",
    swagger_ui_parameters={
        "url": f"{local_configs.server.redirect_openapi_prefix.knowledge_base}/openapi.json",
        "persistAuthorization": local_configs.project.debug,
    },
    servers=[
        {
            "url": str(server.url) + local_configs.server.redirect_openapi_prefix.knowledge_base[1:],
            "description": server.description,
        }
        for server in local_configs.project.swagger_servers
    ],
)

knowledge_base_api.setup_middleware(roster=middleware_roster)
knowledge_base_api.setup_exception_handlers(roster=exception_handler_roster)

knowledge_base_api.amount_app_or_router(roster=[(v1_router, "", "v1")])
knowledge_base_api.amount_app_or_router(roster=[(v2_router, "", "v2")])


@knowledge_base_api.get("/health", summary="健康检查")
async def health() -> dict[str, str]:
    """
    健康检查
    """
    for connection in ConnectionNameEnum:
        await Tortoise.get_connection(connection.value).execute_query("SELECT 1")
    return {"status": "ok"}
