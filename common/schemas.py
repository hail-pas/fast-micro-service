from pydantic import BaseModel, PositiveInt, conint
from tortoise.contrib.pydantic import PydanticModel


class Pager(BaseModel):
    limit: PositiveInt = 10
    offset: conint(ge=0) = 0  # type: ignore


class CRUDPager(Pager):
    order_by: set[str] = set()
    search: str | None = None
    selected_fields: set[str] | None = None
    available_search_fields: set[str] | None = None
    list_schema: type[PydanticModel | BaseModel]
    # available_sort_fields: set[str] | None = None
    # available_search_fields: set[str] | None = None


class IdsSchema(BaseModel):
    ids: set[str]
