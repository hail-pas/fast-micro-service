from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from common.responses import AesResponse


class ConsumerStatus(BaseModel):
    status: str
    last_message: Any = None
    error: str = None


consumer_status = ConsumerStatus(status="initializing")

app = FastAPI()


# 健康检查的HTTP端点
@app.get("/health", response_model=ConsumerStatus)
def health_check() -> AesResponse:
    if consumer_status.status == "error":
        return AesResponse(status_code=500, content=consumer_status.model_dump_json())
    return AesResponse(content=consumer_status.model_dump_json())


def start_http_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)
