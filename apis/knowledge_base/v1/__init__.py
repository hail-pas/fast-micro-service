from fastapi import Depends, Request, APIRouter

from common.utils import gte_all_uris
from common.responses import Resp
from service.dependencies import api_permission_check
from apis.knowledge_base.tags import TagsEnum
from apis.knowledge_base.v1.knowledge_file import router as explain_router

router = APIRouter(prefix="/v1")

router.include_router(
    explain_router, prefix="/explain", tags=[TagsEnum.explain], dependencies=[Depends(api_permission_check)]
)


@router.get("/uri-list", tags=[TagsEnum.root], summary="全部uri")
def get_all_urls_from_request(request: Request) -> Resp[list]:
    return Resp(data=gte_all_uris(request.app))  # type: ignore
