from typing import Generic, TypeVar

from configs.config import local_configs

T = TypeVar("T")


class OssProxy(Generic[T]):

    @classmethod
    def client(
        cls,
        access_key_id: str = local_configs.oss.access_key_id,
        access_key_secret: str = local_configs.oss.access_key_secret,
        endpoint: str = local_configs.oss.endpoint,
        external_endpoint: str = local_configs.oss.external_endpoint,
        bucket_name: str = local_configs.oss.bucket_name,
        cname: bool = local_configs.oss.cname,
        expire_time: int = local_configs.oss.expire_time,
    ) -> T:
        provider_cls: T = None

        match local_configs.oss.provider:
            case "aliyun":
                from storages.oss.provider.aliyun import AliyunOss

                provider_cls = AliyunOss
            case "huaweiyun":
                from storages.oss.provider.huaweiyun import HuaweiyunOss

                provider_cls = HuaweiyunOss
            case "minio":
                from storages.oss.provider.aminio import MinioOss

                provider_cls = MinioOss
        if not provider_cls:
            raise ValueError(f"Unsupported OSS provider: {local_configs.oss.provider}")

        return provider_cls(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            external_endpoint=external_endpoint,
            bucket_name=bucket_name,
            cname=cname,
            expire_time=expire_time,
        )
