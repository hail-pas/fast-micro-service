from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Self
from inspect import isclass, isfunction
from contextlib import asynccontextmanager
from collections.abc import Callable, AsyncGenerator

import loguru
from tortoise import Tortoise
from fastapi import FastAPI, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from common.log import LogLevelEnum, setup_loguru
from common.utils import merge_dict
from configs.config import LocalConfig
from common.responses import AesResponse
from common.monkey_patch import patch


class _ConfigRegistry:
    _config = {
        "loguru_setup_done": False,
        "monkey_patch_done": False,
    }

    @classmethod
    def is_loguru_setup_done(cls) -> bool:
        return cls._config["loguru_setup_done"]

    @classmethod
    def set_loguru_setup_done(cls) -> None:
        cls._config["loguru_setup_done"] = True

    @classmethod
    def is_monkey_patch_done(cls) -> bool:
        return cls._config["monkey_patch_done"]

    @classmethod
    def set_monkey_patch_done(cls) -> None:
        cls._config["monkey_patch_done"] = True


# @asynccontextmanager
# async def lifespan(app: ServiceApi) -> AsyncGenerator:
#     # 初始化及退出清理

#     # tortoise
#     await Tortoise.init(config=app.settings.relational.tortoise_orm_config)

#     yield

#     await Tortoise.close_connections()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # 初始化及退出清理

    # tortoise
    await Tortoise.init(config=app.settings.relational.tortoise_orm_config)

    yield

    await Tortoise.close_connections()


class ServiceApi(FastAPI, ABC):
    code: str
    settings: LocalConfig
    logger: loguru.Logger

    _default_config = {
        "default_response_class": AesResponse,
        "lifespan": lifespan,
    }

    def __init__(self, code: str, title: str, description: str, settings: LocalConfig, **kwargs) -> None:
        if not _ConfigRegistry.is_loguru_setup_done():
            setup_loguru(LogLevelEnum.DEBUG if settings.project.debug else LogLevelEnum.INFO)
            _ConfigRegistry.set_loguru_setup_done()
        if not _ConfigRegistry.is_monkey_patch_done():
            patch()
            _ConfigRegistry.set_monkey_patch_done()
        kwargs = merge_dict(kwargs, self._default_config)
        if "debug" not in kwargs:
            kwargs["debug"] = settings.project.debug
        super().__init__(title=title, description=description, **kwargs)
        # self.code = code.title()
        self.code = code
        self.settings = settings
        self.logger = loguru.logger.bind(code=self.code)

    def enable_sentry(self) -> None:
        if not self.settings.project.sentry_dsn:
            return

        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.redis import RedisIntegration  # type: ignore

        sentry_sdk.init(
            dsn=self.settings.project.sentry_dsn,  # type: ignore
            environment=self.settings.project.environment,  # type: ignore
            integrations=[RedisIntegration()],
        )

    def enable_static_app(self) -> None:
        static_files_app = StaticFiles(
            directory=f"{self.settings.server.static_path}/{self.code}",  # type: ignore
        )
        self.mount(
            path=self.settings.server.static_path,  # type: ignore
            app=static_files_app,
            name="static",
        )

    def amount_app_or_router(self, roster: list[tuple[FastAPI | Self | APIRouter, str, str]]) -> None:
        for app_or_router, prefix_path, name in roster:
            assert not prefix_path or prefix_path.startswith(
                "/",
            ), "Routed paths must start with '/'"
            if isinstance(app_or_router, FastAPI):
                self.mount(prefix_path or "", app_or_router, name)
            elif isinstance(app_or_router, APIRouter):
                self.include_router(app_or_router)
            else:
                raise TypeError(f"Invalid type for roster item: {app_or_router}")

    def setup_middleware(self, roster: list[Any]) -> None:
        for middle_fc in roster[::-1]:
            if isfunction(middle_fc):
                self.add_middleware(BaseHTTPMiddleware, dispatch=middle_fc)
            else:
                if isclass(middle_fc[0]):  # type: ignore
                    if isinstance(middle_fc[1], dict):  # type: ignore
                        self.add_middleware(middle_fc[0], **middle_fc[1])  # type: ignore
                    else:
                        raise RuntimeError(
                            f"Require Dict as kwargs for middleware class, Got {type(middle_fc[1])}",  # type: ignore
                        )
                else:
                    raise RuntimeError(
                        f"Require Class, Got Type {type(middle_fc[0])}",  # type: ignore
                    )

    def setup_exception_handlers(
        self,
        roster: list[tuple[type[Exception], Callable[..., AesResponse | HTMLResponse | None]]],
    ) -> None:
        for exc, handler in roster:
            self.add_exception_handler(exc, handler)  # type: ignore

    @abstractmethod
    async def before_server_start(self) -> None:
        # 生产环境启动前执行代码, 如数据库迁移等
        raise NotImplementedError
