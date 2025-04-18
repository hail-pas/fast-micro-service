import os
import enum
import multiprocessing
from typing import Self, Literal
from pathlib import Path
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from functools import lru_cache
from urllib.parse import unquote
from collections.abc import AsyncGenerator

from pydantic import HttpUrl, MySQLDsn, RedisDsn, BaseModel, ConfigDict, model_validator
from redis.retry import Retry
from redis.asyncio import Redis, ConnectionPool
from redis.backoff import NoBackoff


class EnvironmentEnum(str, enum.Enum):
    local = "local"
    development = "development"
    test = "test"
    production = "production"


ENVIRONMENT = os.environ.get(
    "environment",  # noqa
    EnvironmentEnum.local.value,
)

BASE_DIR = Path(__file__).resolve().parent.parent


class ConnectionNameEnum(str, enum.Enum):
    """数据库连接名称"""

    # default = "default"  # "默认连接"
    user_center = "user_center"  # "用户中心连接"
    knowledge_base = "knowledge_base"  # "知识库连接"


VersionFilePath: str = f"{BASE_DIR}/storages/relational/migrate/"


class Relational(BaseModel):
    user_center: MySQLDsn
    knowledge_base: MySQLDsn

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo("Asia/Shanghai")

    @property
    def tortoise_orm_config(self) -> dict:
        echo = False
        return {
            "connections": {
                ConnectionNameEnum.user_center.value: {
                    # "engine": "tortoise.backends.sqlite",
                    # "credentials": {"file_path": ":memory:"},
                    "engine": "tortoise.backends.mysql",
                    "credentials": {
                        "host": self.user_center.host,
                        "port": self.user_center.port,
                        "user": self.user_center.username,
                        "password": unquote(self.user_center.password) if self.user_center.password else "",
                        "database": self.user_center.path.strip("/"),  # type: ignore
                        "echo": echo,
                        "minsize": 1,  # 连接池的最小连接数
                        "maxsize": 10,  # 连接池的最大连接数
                        "pool_recycle": 3600,  # 连接的最大存活时间（秒）
                    },
                },
                ConnectionNameEnum.knowledge_base.value: {
                    # "engine": "tortoise.backends.sqlite",
                    # "credentials": {"file_path": ":memory:"},
                    "engine": "tortoise.backends.mysql",
                    "credentials": {
                        "host": self.knowledge_base.host,
                        "port": self.knowledge_base.port,
                        "user": self.knowledge_base.username,
                        "password": unquote(self.knowledge_base.password) if self.knowledge_base.password else "",
                        "database": self.knowledge_base.path.strip("/"),  # type: ignore
                        "echo": echo,
                        "minsize": 1,  # 连接池的最小连接数
                        "maxsize": 10,  # 连接池的最大连接数
                        "pool_recycle": 3600,  # 连接的最大存活时间（秒）
                    },
                },
            },
            "apps": {
                ConnectionNameEnum.user_center.value: {
                    "models": [
                        "aerich.models",
                        "storages.relational.models.user_center",
                    ],
                    "default_connection": ConnectionNameEnum.user_center.value,
                },
                ConnectionNameEnum.knowledge_base.value: {
                    "models": [
                        "storages.relational.models.knowledge_base",
                    ],
                    "default_connection": ConnectionNameEnum.knowledge_base.value,
                },
            },
            # "use_tz": True,   # Will Always Use UTC as Default Timezone
            "timezone": "Asia/Shanghai",
            # 'routers': ['path.router1', 'path.router2'],
        }


class RedisConfig(BaseModel):
    user_center: RedisDsn
    knowledge_base: RedisDsn
    celery_broker: RedisDsn
    celery_backend: RedisDsn
    max_connections: int = 10

    def connection_pool(self, service: ConnectionNameEnum) -> ConnectionPool:
        @lru_cache()
        def _create_redis_pool(_service: ConnectionNameEnum) -> ConnectionPool:
            return ConnectionPool.from_url(
                url=str(getattr(self, _service.value)),
                max_connections=self.max_connections,
                decode_responses=True,
                encoding_errors="strict",
                retry=Retry(NoBackoff(), retries=10),
                health_check_interval=30,
            )

        return _create_redis_pool(service)


    @asynccontextmanager
    async def get_redis(self, service: ConnectionNameEnum, **kwargs) -> AsyncGenerator[Redis, None]:  # type: ignore
        try:
            r: Redis = Redis(
                connection_pool=self.connection_pool(service),
                **kwargs,
            )
            yield r
        finally:
            await r.close()


class CorsConfig(BaseModel):
    allow_origins: list[str] = ["*"]
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]
    expose_headers: list[str] = []

    @property
    def headers(self) -> dict:
        result = {
            "Access-Control-Allow-Origin": ",".join(self.allow_origins) if "*" not in self.allow_origins else "*",
            "Access-Control-Allow-Credentials": str(
                self.allow_credentials,
            ).lower(),
            "Access-Control-Expose-Headers": ",".join(self.allow_headers) if "*" not in self.allow_headers else "*",
            "Access-Control-Allow-Methods": ",".join(self.allow_methods) if "*" not in self.allow_methods else "*",
        }
        if self.expose_headers:
            result["Access-Control-Expose-Headers"] = ", ".join(
                self.expose_headers,
            )

        return result


class ProfilingConfig(BaseModel):
    secret: str
    interval: float = 0.001


class ServiceStringConfig(BaseModel):
    user_center: str
    knowledge_base: str


class Server(BaseModel):
    address: HttpUrl = HttpUrl("http://0.0.0.0:8000")
    cors: CorsConfig = CorsConfig()
    worker_number: int = multiprocessing.cpu_count() * int(os.getenv("WORKERS_PER_CORE", "2")) + 1
    profiling: ProfilingConfig | None = None
    allow_hosts: list = ["*"]
    static_path: str = "/static"
    docs_uri: str = "/docs"
    redoc_uri: str = "/redoc"
    openapi_uri: str = "/openapi.json"
    token_expire_seconds: int = 3600 * 24 * 7  # 7天

    redirect_openapi_prefix: ServiceStringConfig = ServiceStringConfig(
        user_center="/user",
        knowledge_base="/kb",
    )


class Project(BaseModel):
    unique_code: ServiceStringConfig = ServiceStringConfig(
        user_center="UserCenter",
        knowledge_base="KnowledgeBase",
    )
    debug: bool = False
    environment: EnvironmentEnum = EnvironmentEnum.production
    sentry_dsn: HttpUrl | None = None

    class SwaggerServerConfig(BaseModel):
        url: HttpUrl
        description: str

    swagger_servers: list[SwaggerServerConfig] = []

    @model_validator(mode="after")
    def check_debug_options(self) -> Self:
        assert not (
            self.debug and self.environment == EnvironmentEnum.production
        ), "Production cannot set with debug enabled"
        return self

    @property
    def base_dir(self) -> Path:
        return BASE_DIR


class OssConfig(BaseModel):
    provider: Literal["aliyun", "huaweiyun", "minio"] = "aliyun"
    access_key_id: str
    access_key_secret: str
    endpoint: str
    external_endpoint: str = ""
    cname: bool = False
    bucket_name: str
    expire_time: int = 3600 * 24 * 30  # 30天


class Third(BaseModel): ...
