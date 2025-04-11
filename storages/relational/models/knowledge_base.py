from tortoise import fields

from configs.defines import ConnectionNameEnum
from storages.relational.base.models import BaseModel


class KnowledgeFile(BaseModel):
    filename = fields.CharField(max_length=255, description="文件名")
    ext = fields.CharField(max_length=10, description="文件扩展名")
    size = fields.IntField(description="文件大小")
    url = fields.CharField(max_length=255, description="文件存储地址")
    file_type = fields.CharField(max_length=50, description="文件类型")
    info_id = fields.IntField(description="知识库ID")

    class Meta:
        table_description = "文件表"
        ordering = ["-id"]
        app = ConnectionNameEnum.knowledge_base.value
