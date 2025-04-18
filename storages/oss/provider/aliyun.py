import os
from itertools import islice
from urllib.parse import urljoin
from collections.abc import Iterable

import oss2
from oss2.exceptions import AccessDenied, NoSuchBucket
from typing_extensions import override

from common.utils import clean_path, normalize_url
from configs.config import local_configs
from common.decorators import singleton
from storages.oss.provider.file import OssBase


class BucketOperationMixin:
    def _get_bucket(self, auth: oss2.Auth) -> oss2.Bucket:
        if self.cname:  # type: ignore
            bucket = oss2.Bucket(
                auth,
                self.cname,  # type: ignore
                self.bucket_name,  # type: ignore
                is_cname=True,
            )
        else:
            bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)  # type: ignore

        try:
            bucket.get_bucket_info()
        except NoSuchBucket as e:
            raise ValueError(f"{self.bucket_name} don't exist!") from e  # type: ignore
        else:
            return bucket

    def _list_bucket(self, service: oss2.Service) -> list[str]:
        return [bucket.name for bucket in oss2.BucketIterator(service)]

    def _list_prefix_bucket(
        self,
        service: oss2.Service,
        prefix: str,
    ) -> list[oss2.Bucket]:
        return [bucket.name for bucket in oss2.BucketIterator(service, prefix=prefix)]

    def _create_bucket(self, auth: oss2.Auth) -> oss2.Bucket:
        bucket = self._get_bucket(auth)
        bucket.create_bucket(local_configs.OSS.BUCKET_ACL_TYPE)  # type: ignore
        return bucket


@singleton(
    key_generator=lambda **kwargs: f"{kwargs.get('endpoint', '')}:{kwargs.get('bucket_name', '')}:{kwargs.get('access_key_id', '')}"
)
class AliyunOss(
    OssBase,
    BucketOperationMixin,
):

    def __init__(
        self,
        access_key_id: str = local_configs.oss.access_key_id,
        access_key_secret: str = local_configs.oss.access_key_secret,
        endpoint: str = local_configs.oss.endpoint,
        external_endpoint: str = local_configs.oss.external_endpoint,
        bucket_name: str = local_configs.oss.bucket_name,
        cname: bool = local_configs.oss.cname,
        expire_time: int = local_configs.oss.expire_time,
    ) -> None:
        return
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = normalize_url(endpoint)
        self.external_endpoint = None
        if external_endpoint:
            self.external_endpoint = normalize_url(external_endpoint)
        self.bucket_name = bucket_name
        self.cname = cname
        self.default_expire_time = expire_time

        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        self.service = oss2.Service(self.auth, self.endpoint)
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)

        try:
            if self.bucket_name not in self._list_bucket(self.service):
                # self.bucket = self._create_bucket(self.auth)
                raise ValueError(
                    "Bucket '%s' does not exist." % self.bucket_name,
                )
            # change bucket acl if not consists
            self.bucket = self._get_bucket(self.auth)
            self.bucket_acl = self.bucket.get_bucket_acl().acl
            if self.bucket_acl == "private" and self.bucket_acl != local_configs.OSS.BUCKET_ACL_TYPE:  # type: ignore
                raise ValueError(
                    "Acl '{}' of Bucket '{}' does not match config '{}'.".format(
                        *self.bucket_acl,
                    ),
                    self.bucket_name,
                    local_configs.OSS.BUCKET_ACL_TYPE,  # type: ignore
                )
        except AccessDenied:
            # 当启用了RAM访问策略，是不允许list和create bucket的
            self.bucket = self._get_bucket(self.auth)
        # auth = oss2.AnonymousAuth()

    def _normalize_name(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> str:
        """规范化路径"""

        base_path = base_path if base_path else "/"
        base_path = base_path.rstrip("/")

        final_path = urljoin(base_path + "/", filepath)

        base_path_len = len(base_path)
        if not final_path.startswith(base_path) or final_path[base_path_len : base_path_len + 1] not in (
            "",
            "/",
        ):  # noqa
            raise ValueError("Attempted access to '%s' denied." % filepath)
        return final_path.lstrip("/")

    @override
    def get_real_path(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> str:
        return self._normalize_name(clean_path(filepath), base_path)

    def create_file(
        self,
        filepath: str,
        content: bytes,
        base_path: str | None = None,
        headers: dict | oss2.CaseInsensitiveDict | None = None,
        progress_callback: str | None = None,
    ) -> tuple[bool, str]:
        """内容上传创建文件

        Args:
            filepath (str): oss文件路径
            content (bytes): 文件内容
            base_path (str | None): 前缀路径
            headers (dict | oss2.CaseInsensitiveDict | None): 请求头
            progress_callback (str | None): 回调

        Returns:
            tuple[bool, str]: 成功标识, url
        """
        key = self.get_real_path(filepath, base_path)
        try:
            response = self.bucket.put_object(
                key,
                content,
                headers=headers,
                progress_callback=progress_callback,
            )
            return True, response.resp.response.url
        except Exception as e:
            return False, f"Upload File To Oss Failed! Error:{e}"

    def create_file_from_local(
        self,
        filepath: str,
        target_path: str,
        base_path: str | None = None,
        headers: dict | oss2.CaseInsensitiveDict | None = None,
        progress_callback: str | None = None,
    ) -> tuple[bool, str]:
        """上传本地文件

        Args:
            filepath (str): oss文件路径
            local_file_path (str): 本地文件路径
            base_path (str | None): 前缀路径
            headers (dict | oss2.CaseInsensitiveDict | None): 请求头
            progress_callback (str | None): 回调

        Returns:
            tuple[bool, str]: 成功标识, url
        """
        key = self.get_real_path(filepath, base_path)
        try:
            target_path = self._normalize_name(clean_path(target_path))
            response = self.bucket.put_object_from_file(
                key,
                target_path,
                headers=headers,
                progress_callback=progress_callback,
            )
            return True, response.resp.response.url
        except Exception as e:
            return False, f"Upload Import File To Oss Fail! Error:{e}"

    def exists(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> bool:
        key = self.get_real_path(filepath, base_path)
        return self.bucket.object_exists(key)  # type: ignore

    def get_file_header(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> dict:
        key = self.get_real_path(filepath, base_path)
        return self.bucket.head_object(key)  # type: ignore

    def delete_file(
        self,
        filepath: str,
        base_path: str | None = None,
        params: dict | None = None,
        headers: dict | oss2.CaseInsensitiveDict | None = None,
    ) -> tuple[bool, str]:
        """删除文件

        Args:
            filepath (str): oss文件路径
            base_path (str | None): 前缀路径
            params (dict | None): 请求参数
            headers (dict | oss2.CaseInsensitiveDict | None): 请求头

        Returns:
            tuple[bool, str]: 成功标识, url
        """
        key = self.get_real_path(filepath, base_path)
        try:
            self.bucket.delete_object(key, params=params, headers=headers)
            return True, ""
        except Exception as e:
            return False, f"Delete File From Oss Failed! Error:{e}"

    def download_file(
        self,
        filepath: str,
        base_path: str | None = None,
        target_path: str | None = None,
    ) -> tuple[bool, str]:
        key = self.get_real_path(filepath, base_path)
        filename = key.split("/")[-1]
        try:
            if not self.bucket.object_exists(filepath):
                return False, f"oss文件: {filepath}不存在"
            path = target_path if target_path else f"./{self.get_random_filename(filename)}"

            path = self._normalize_name(clean_path(path))

            if os.path.exists(path):
                return False, "目标文件路径已被占用"

            if not os.path.exists(os.path.dirname(path)):
                os.mkdir(os.path.dirname(path))

            self.bucket.get_object_to_file(filepath, path)
            return True, path
        except Exception as e:
            return False, f"Download File From Oss Failed! Error:{e}"

    def get_file_object(
        self,
        filepath: str,
        base_path: str | None = None,
    ) -> tuple[bool, bytes | str]:
        key = self.get_real_path(filepath, base_path)
        try:
            if not self.bucket.object_exists(key):
                return False, f"oss文件: {key}不存在"
            file_object = self.bucket.get_object(key)
            return True, file_object.resp.response.content
        except Exception as e:
            return False, f"Get File Object From Oss Failed! Error:{e}"

    def get_file_list_iter(self, batch_size: int = 20) -> Iterable:
        """查看文件列表"""
        return islice(oss2.ObjectIterator(self.bucket), batch_size)

    def get_download_url(
        self,
        filepath: str,
        expires: int = 10 * 60,
        headers: dict | oss2.CaseInsensitiveDict | None = None,
        params: dict | None = None,
        slash_safe: bool = True,
        base_path: str | None = None,
    ) -> tuple[bool, str]:
        """获取下载url"""
        key = self.get_real_path(filepath, base_path)
        try:
            return True, self.bucket.sign_url(
                method="GET",
                key=key,
                expires=expires,
                headers=headers,
                params=params,
                slash_safe=slash_safe,
            )
        except Exception as e:
            return False, "Generate Temp Download URL Failed! Error:{}".format(
                e,
            )

    def get_perm_download_url(
        self,
        filepath: str,
        slash_safe: bool = True,
        base_path: str | None = None,
    ) -> tuple[bool, str]:
        key = self.get_real_path(filepath, base_path)
        try:
            return self.bucket._make_url(  # type: ignore
                self.bucket_name,
                key,
                slash_safe=slash_safe,
            )
        except Exception as e:
            return False, "Generate Perm Download URL Failed! Error:{}".format(
                e,
            )

    def get_upload_url(
        self,
        filepath: str,
        expires: int = 2 * 60,
        headers: dict | oss2.CaseInsensitiveDict | None = None,
        params: dict | None = None,
        slash_safe: bool = True,
        base_path: str | None = None,
    ) -> tuple[bool, str]:
        """获取上传url"""
        key = self.get_real_path(filepath, base_path)
        try:
            return True, self.bucket.sign_url(
                method="PUT",
                key=key,
                expires=expires,
                headers=headers,
                params=params,
                slash_safe=slash_safe,
            )
        except Exception as e:
            return False, f"Generate Temp Upload URL Failed! Error:{e}"

    @override
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

    @override
    def list_keys(self, prefix, max_keys=1000):
        return [i.key for i in self.bucket.list_objects(prefix=prefix, max_keys=max_keys).object_list]
