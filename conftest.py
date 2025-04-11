import pytest
from faker import Faker
from httpx import AsyncClient, ASGITransport
from loguru import logger
from tortoise import Tortoise

from configs.config import local_configs
from configs.defines import ConnectionNameEnum
from apis.entrypoint.factory import service_api as app



async def init_db(create_db: bool = False, schemas: bool = False) -> None:
    """Initial database connection"""
    logger.info(f"local_configs.relational.tortoise_orm_config: {local_configs.relational.tortoise_orm_config}")
    await Tortoise.init(config=local_configs.relational.tortoise_orm_config, _create_db=create_db)
    for connection in ConnectionNameEnum:
        await Tortoise.get_connection(connection.value).execute_query("SELECT 1")

    # if schemas:
    #     await Tortoise.generate_schemas()
    #     print("Success to generate schemas")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        print("Client is ready")
        yield client


@pytest.fixture(scope="session")
def token(client: AsyncClient):
    # response = await client.post("/user/v1/auth/login", json={"username": "admin", "password": "123456"})
    # return response.json()["data"]["token"]
    return "Bearer 7e47ca5e84ac42d4884a9e65b64219df"


@pytest.fixture(scope="session", autouse=True)
async def initialize_tests():
    await init_db()
    yield
    # await Tortoise._drop_databases()


@pytest.fixture(scope="session")
def fake():
    return Faker("zh_CN")
