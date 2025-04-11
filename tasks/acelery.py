from celery import Celery
from kombu import Queue

from configs.config import local_configs

class QueueNameEnum:
    default = "default"
    highPriority = "highPriority"

local_configs.redis

celery_app = Celery(
    "MainService",
    broker=local_configs.redis.celery_broker,
    backend=local_configs.redis.celery_backend,
)


celery_app.conf.task_queues = (
    Queue(QueueNameEnum.default, routing_key=QueueNameEnum.default),
    Queue(QueueNameEnum.highPriority, routing_key=QueueNameEnum.highPriority),
)
