import os
from urllib.parse import urljoin
from collections.abc import Iterable

from obs import ObsClient
from obs.client import BucketClient

from common.utils import clean_path, normalize_url
from configs.config import local_configs
from common.decorators import singleton
from storages.oss.provider.file import OssBase


@singleton(
    key_generator=lambda **kwargs: f"{kwargs.get('endpoint', '')}:{kwargs.get('bucket_name', '')}:{kwargs.get('access_key_id', '')}"
)
class HuaweiyunOss(
    OssBase,
):
    _base_path = "/"

    def __init__(
        self,
        access_key_id: str = local_configs.oss.access_key_id,  # type: ignore
        access_key_secret: str = local_configs.oss.access_key_secret,  # type: ignore
        endpoint: str = local_configs.oss.endpoint,  # type: ignore
        external_endpoint: str = local_configs.OSS.EXTERNAL_ENDPOINT,
        bucket_name: str = local_configs.oss.bucket_name,  # type: ignore
        cname: bool = local_configs.OSS.CNAME,  # type: ignore
        expire_time: int = local_configs.oss.expire_time,  # type: ignore
    ) -> None:
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = normalize_url(endpoint)
        # self.external_endpoint = None
        # if external_endpoint:
        #     self.external_endpoint = normalize_url(external_endpoint)
        self.bucket_name = bucket_name
        self.default_expire_time = expire_time

        self.client = ObsClient(
            access_key_id=access_key_id,
            secret_access_key=access_key_secret,
            server=endpoint,
            is_secure=False,
            signature="obs",
        )
        self.bucket: BucketClient = self.client.bucketClient(self.bucket_name)

    def _normalize_name(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> str:
        """规范化路径"""

        base_path = base_path if base_path else self._base_path
        base_path = base_path.rstrip("/")

        final_path = urljoin(base_path + "/", filepath)

        base_path_len = len(base_path)
        if not final_path.startswith(base_path) or final_path[base_path_len : base_path_len + 1] not in (
            "",
            "/",
        ):  # noqa
            raise ValueError(f"Attempted access to '{filepath}' denied.")
        return final_path.lstrip("/")

    def get_real_path(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> str:
        return self._normalize_name(clean_path(filepath), base_path)

    def create_file(
        self,
        filepath: str,
        content: bytes | str,
        base_path: str | None = None,
        headers: dict | None = None,
        progress_callback: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[bool, str]:
        """内容上传创建文件"""
        key = self.get_real_path(filepath, base_path)
        try:
            response = self.client.putContent(
                bucketName=self.bucket_name,
                objectKey=key,
                content=content,
                metadata=metadata,
                headers=headers,
                progressCallback=progress_callback,
            )
            if response.status < 300:
                return True, response.body.objectUrl
            return (
                False,
                f"Upload File To Oss Failed! Error:{response.errorCode}-{response.errorMessage}",
            )
        except Exception as e:
            return False, f"Upload File To Oss Failed! Error:{e}"

    def create_file_from_local(
        self,
        filepath: str,
        target_path: str,
        base_path: str | None = None,
        metadata: dict | None = None,
        headers: dict | None = None,
        progress_callback: str | None = None,
    ) -> tuple[bool, str]:
        """上传本地文件"""
        key = self.get_real_path(filepath, base_path)
        try:
            # target_path = self._normalize_name(clean_path(target_path))
            response = self.client.putFile(
                bucketName=self.bucket_name,
                objectKey=key,
                file_path=target_path,
                metadata=metadata,
                headers=headers,
                progressCallback=progress_callback,
            )
            if response.status < 300:
                return True, response.body.objectUrl
            return (
                False,
                f"Upload File To Oss Failed! Error:{response.errorCode}-{response.errorMessage}",
            )
        except Exception as e:
            return False, f"Upload Import File To Oss Fail! Error:{e}"

    def exists(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> bool:
        if self.get_file_header(filepath, base_path):  # noqa: SIM103
            return True
        return False

    def get_file_header(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> dict:
        key = self.get_real_path(filepath, base_path)
        response = self.client.getObjectMetadata(
            bucketName=self.bucket_name,
            objectKey=key,
        )
        if response.status < 300:
            return response.body or {}  # type: ignore
        return {}

    def delete_file(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> tuple[bool, str]:
        """删除文件"""
        key = self.get_real_path(filepath, base_path)
        try:
            response = self.client.deleteObject(
                bucketName=self.bucket_name,
                objectKey=key,
            )
            if response.status < 300:
                return True, ""
            return (
                False,
                f"Delete File From Oss Failed! Error:{response.errorCode}-{response.errorMessage}",
            )
        except Exception as e:
            return False, f"Delete File From Oss Failed! Error:{e}"

    def download_file(
        self,
        filepath: str,
        base_path: str | None = None,
        target_path: str | None = None,
        headers: dict | None = None,
    ) -> tuple[bool, str]:
        key = self.get_real_path(filepath, base_path)
        filename = key.split("/")[-1]
        try:
            path = target_path if target_path else f"./{self.get_random_filename(filename)}"

            path = self._normalize_name(clean_path(path))

            if os.path.exists(path):
                return False, "目标文件路径已被占用"

            if not os.path.exists(os.path.dirname(path)):
                os.mkdir(os.path.dirname(path))

            response = self.client.getObject(
                bucketName=self.bucket_name,
                objectKey=key,
                downloadPath=path,
                headers=headers,
            )
            if response.status < 300:
                return True, path
            return (
                False,
                f"Download File From Oss Failed! Error:{response.errorCode}-{response.errorMessage}",
            )

        except Exception as e:
            return False, f"Download File From Oss Failed! Error:{e}"

    def get_file_object(
        self,
        filepath: str,
        base_path: str | None = None,
        headers: dict | None = None,
    ) -> tuple[bool, bytes | str]:
        key = self.get_real_path(filepath, base_path)
        try:
            response = self.client.getObject(
                bucketName=self.bucket_name,
                objectKey=key,
                headers=headers,
                loadStreamInMemory=True,
            )
            if response.status < 300:
                return True, response.body.buffer
            return (
                False,
                f"Get File Object From Oss Failed! Error:{response.errorCode}-{response.errorMessage}",
            )

        except Exception as e:
            return False, f"Get File Object From Oss Failed! Error:{e}"

    def get_file_list_iter(
        self,
        prefix: str | None = None,
        max_keys: int = 100,
    ) -> Iterable:
        """查看文件列表"""
        response = self.client.listObjects(
            bucketName=self.bucket_name,
            prefix=prefix,
            max_keys=max_keys,
        )
        yield from response.body.contents

    def get_download_url(  # type: ignore
        self,
        filepath: str,
        expires: int = 10 * 60,
        headers: dict | None = None,
        params: dict | None = None,
        base_path: str | None = None,
    ) -> tuple[bool, str]:
        """获取下载url"""
        try:
            key = self.get_real_path(filepath, base_path)
            response = self.client.createSignedUrl(
                method="GET",
                bucketName=self.bucket_name,
                objectKey=key,
                expires=expires,
                headers=headers,
                queryParams=params,
            )
            url = response["signedUrl"].replace("http://", "https://")
            return (
                True,
                url,
            )
            # response["actualSignedRequestHeaders"],
        except Exception as e:
            return False, f"Generate Temp Download URL Failed! Error:{e}"

    # def get_perm_download_url(
    #     self,
    #     filepath: str,
    #     base_path: str | None = None,
    #     headers: dict | None = None,
    #     params: dict | None = None,
    # ) -> tuple[bool, str]:
    #     key = self.get_real_path(filepath, base_path)
    #     try:
    #         response = self.client.createSignedUrl( # 默认为300
    #             method="GET",
    #             bucketName=self.bucket_name,
    #             objectKey=key,
    #             headers=headers,
    #             queryParams=params,
    #         )
    #         return True, response["signedUrl"],
    #             # response["actualSignedRequestHeaders"],
    #     except Exception as e:
    #         return False, "Generate Perm Download URL Failed! Error:{}".format(
    #             e,
    #         )

    def get_upload_url(
        self,
        filepath: str,
        expires: int = 2 * 60,
        headers: dict | None = None,
        params: dict | None = None,
        base_path: str | None = None,
    ) -> tuple[bool, str]:
        """获取上传url
        headers = {'Content-Length': str(len(content))}
        """
        key = self.get_real_path(filepath, base_path)
        try:
            response = self.client.createSignedUrl(
                method="PUT",
                bucketName=self.bucket_name,
                objectKey=key,
                expires=expires,
                headers=headers,
                queryParams=params,
            )
            return True, response["signedUrl"]
            # response["actualSignedRequestHeaders"]
        except Exception as e:
            return False, f"Generate Temp Upload URL Failed! Error:{e}"

    def get_full_path(
        self,
        filepath: str,
        expires: int | None = None,
    ) -> tuple[bool, str]:
        if expires is None:
            expires = 10 * 60
        return self.get_download_url(
            filepath=filepath,
            base_path="/",
            expires=expires,
        )
