import pytest
from faker import Faker
from httpx import AsyncClient

path_prefix = "/user/v1"  # API路径前缀


@pytest.mark.anyio
class TestUser:
    async def test_list(self, token: str, client: AsyncClient, fake: Faker):
        ...

    async def test_create_update_delete(self, token: str, client: AsyncClient, fake: Faker):
        ...
