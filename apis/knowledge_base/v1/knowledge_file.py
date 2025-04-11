from fastapi import Depends, Request, APIRouter
from pydantic import Field, BaseModel

from common.responses import Resp
from service.dependencies import token_required

router = APIRouter(
    prefix="/common",
    dependencies=[Depends(token_required)],
)


class ExplainSetupSchema(BaseModel):
    collection_name: str = Field(
        title="知识库名称",
        description="知识库名称",
        example="knowledge_base",
    )
    file_ids: list[int] = Field(
        title="文件ID",
        description="文件ID列表",
        example=[1, 2, 3],
    )


@router.post(
    "/setup",
    description="知识库整体解析",
    summary="知识库整体解析",
)
async def explain_setup(request: Request, schema: ExplainSetupSchema) -> Resp:
    return Resp(data="ok")  # type: ignore


@router.post(
    "/retry",
    description="文件重新解析",
    summary="文件重新解析",
)
async def explain_retry(request: Request, schema: ExplainSetupSchema) -> Resp:
    return Resp(data="ok")  # type: ignore


@router.post(
    "/re-chunking",
    description="文件重新分块",
    summary="文件重新分块",
)
async def explain_re_chunking(request: Request, schema: ExplainSetupSchema) -> Resp:
    return Resp(data="ok")  # type: ignore
