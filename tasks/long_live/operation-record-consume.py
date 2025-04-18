"""
消费 kafka 操作记录 topic
"""

import asyncio
import threading
from uuid import UUID
from typing import Literal
from datetime import datetime

import orjson
from loguru import logger
from pydantic import Field, BaseModel

from configs.config import local_configs
from common.init_ctx import init_ctx
from tasks.consumer_health_check import consumer_status, start_http_server
from storages.relational.models.user_center import Account

sink: Literal["mysql",] = "mysql"


class OperationRecordDictV1(BaseModel):
    unique_id: UUID = Field(description="唯一标识")
    account_id: UUID = Field(description="账户ID")
    role_name: str | None = Field(default=None, description="角色名称")
    # role_name: str = Field(description="角色名称")
    # created_at: datetime = Field(description="创建时间")
    # updated_at: datetime = Field(description="更新时间")
    operation_time: datetime = Field(description="操作时间")

    item: str = Field(description="操作对象+动作")
    extra_description: str = Field(description="额外信息")


async def init():
    await init_ctx()


async def msg_handler(msg: dict) -> None:
    try:
        parsed_msg = orjson.loads(msg.value)
        logger.info(f"received message: {parsed_msg}")
        data = OperationRecordDictV1(**parsed_msg)
    except Exception as e:
        logger.error(f"failed to parse message: {msg.value}, error: {e}")
        return

    if not data.item:
        logger.warning(f"missing item: {data}")
        return

    account: Account | None = await Account.get_or_none(id=data.account_id).prefetch_related("role")
    if not account:
        logger.warning(f"missing account: {data}")
        return
    role = account.role
    data.role_name = role.label

    if not data.response_data:
        data.response_data = {}
    if not data.request_data:
        data.request_data = {}

    if sink == "mysql":
        from storages.relational.models.user_center import OperationRecord

        await OperationRecord.create(
            **data.model_dump(),
        )
        logger.info(f"success consume: {data}")


async def consume() -> None:
    # 初始化 logger、redis、mysql 和 kafka
    await init()

    consumer = ""

    while True:
        try:
            if last_msg:
                logger.info("retrying last message")
                await msg_handler(last_msg)  # 重试错误数据
            async for msg in consumer:
                last_msg = msg
                await msg_handler(msg)
                if not local_configs.kafka.enable_auto_commit:
                    await consumer.commit()
                consumer_status.last_message = msg.value.decode()
                last_msg = None
        except Exception as e:
            logger.error(f"Consume encounter an error: {e}. Retrying after 5 seconds.")
            consumer_status.status = "error"
            consumer_status.error = str(e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server)
    http_thread.daemon = True
    http_thread.start()
    # asyncio.run(consume())
    # 启动Kafka消费者
    loop = asyncio.get_event_loop()
    loop.run_until_complete(consume())
