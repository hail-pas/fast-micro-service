import os
import hmac
import base64
import binascii
from typing import Any, Generic, TypeVar
from collections.abc import Mapping

import orjson
from jose import jwt, constants
from pydantic import BaseModel
from Cryptodome import Random
from Cryptodome.Hash import MD5, SHA1, SHA256
from passlib.context import CryptContext  # type: ignore
from Cryptodome.Cipher import AES, PKCS1_v1_5
from Cryptodome.PublicKey import RSA
from Cryptodome.Signature import pkcs1_15 as SIGN_PKCS1_15
from Cryptodome.Util.Padding import pad, unpad


class AESUtil:
    """aes 加密与解密."""

    def __init__(
        self,
        key: str,
        style: str = "pkcs7",
        mode: int = AES.MODE_ECB,
    ) -> None:
        """128位（16字节）、192位（24字节）或256位（32字节）"""
        self.mode = mode
        self.style = style
        self.key = key.encode()

    def encrypt_data(self, data: str) -> str:
        aes = AES.new(self.key, self.mode)  # type: ignore
        pad_data = pad(data.encode(), AES.block_size, style=self.style)
        return str(
            base64.encodebytes(aes.encrypt(pad_data)),
            encoding="utf8",
        ).replace("\n", "")

    def decrypt_data(self, data: str) -> str:
        aes = AES.new(self.key, self.mode)  # type: ignore
        pad_data = pad(data.encode(), AES.block_size, style=self.style)
        return str(
            unpad(
                aes.decrypt(base64.decodebytes(pad_data)),
                block_size=AES.block_size,
            ).decode("utf8"),
        )

    @staticmethod
    def generate_key(length: int = 256) -> str:
        random_key = os.urandom(length)
        private_key = SHA256.new(random_key).digest()
        return base64.b64encode(private_key).decode()


class AESUtilHex(AESUtil):
    """
    aes 加密与解密
    """

    def encrypt_data(self, data: str) -> str:
        data: bytes = data.encode()  # type: ignore
        aes = AES.new(self.key, self.mode)  # type: ignore
        pad_data = pad(data, AES.block_size, style=self.style)  # type: ignore
        return binascii.hexlify(aes.encrypt(pad_data)).decode()

    def decrypt_data(self, data: str) -> str:
        data = binascii.unhexlify(data)  # type: ignore
        aes = AES.new(self.key, self.mode)  # type: ignore
        return unpad(aes.decrypt(data), AES.block_size).decode()


class RSAUtil:
    """RSA 加密 签名.

    generate key:
        openssl genrsa -out jwt-key 4096
        openssl rsa -in jwt-key -pubout -out jwt-key.pub
    """

    private_key: RSA.RsaKey
    pub_key: RSA.RsaKey

    en_decrypt_module = PKCS1_v1_5
    sign_nodule = SIGN_PKCS1_15

    def __init__(
        self,
        pub_key_path: str,
        private_key_path: str,
    ) -> None:
        if pub_key_path:
            with open(private_key_path, "rb") as f:
                self.private_key = RSA.import_key(f.read())
        if private_key_path:
            with open(pub_key_path, "rb") as f:
                self.pub_key = RSA.import_key(f.read())

    def encrypt(self, text: str, length: int = 200) -> str:
        """Rsa 加密."""
        cipher = PKCS1_v1_5.new(self.pub_key)
        res = []
        for i in range(0, len(text), length):
            text_item = text[i : i + length]
            cipher_text = cipher.encrypt(text_item.encode(encoding="utf-8"))
            res.append(cipher_text)
        return base64.b64encode(b"".join(res)).decode()

    def decrypt(self, text: str) -> str:
        """Rsa 解密."""
        cipher = PKCS1_v1_5.new(self.private_key)
        return cipher.decrypt(
            base64.b64decode(text),
            Random.new().read(15 + SHA1.digest_size),
        ).decode()

    def gen_sign_str(self, data: dict) -> str:
        params_str = ""
        if not data:
            return params_str
        if not isinstance(data, dict):
            raise TypeError("dict required")
        # for k in sorted(data.keys()):
        #     params_str += str(k)+ str(data[k])
        params_str = orjson.dumps(data, option=orjson.OPT_SORT_KEYS).decode()
        return params_str

    def sign(self, data: dict) -> str:
        """Rsa 签名."""
        text = self.gen_sign_str(data)
        raw_sign = SIGN_PKCS1_15.new(self.private_key).sign(
            SHA256.new(text.encode()),
        )
        return MD5.new(raw_sign).hexdigest()

    def verify(self, sign: str, data: dict) -> bool:
        """验签."""
        text = self.gen_sign_str(data)
        try:
            SIGN_PKCS1_15.new(self.pub_key).verify(
                SHA256.new(text.encode()),
                base64.b64decode(sign),
            )
            return True
        except (ValueError, TypeError):
            return False


class HashUtil:
    @staticmethod
    def md5_encode(s: str) -> str:
        """md5加密, 16进制."""
        m = MD5.new(s.encode(encoding="utf-8"))
        return m.hexdigest()

    @staticmethod
    def hmac_sha256_encode(k: str, s: str) -> str:
        """Hmac sha256加密, 16进制."""
        return hmac.digest(k.encode(), s.encode(), "sha256").hex()

    @staticmethod
    def sha1_encode(s: str) -> str:
        """sha1加密, 16进制."""
        m = SHA1.new(s.encode(encoding="utf-8"))
        return m.hexdigest()


class HashUtilB64:
    @staticmethod
    def md5_encode_b64(s: str) -> str:
        """md5加密，base64编码."""
        return base64.b64encode(
            HashUtil.md5_encode(s).encode(),
        ).decode("utf-8")

    @staticmethod
    def hmac_sha256_encode_b64(k: str, s: str) -> str:
        """hmacsha256加密，base64编码."""
        return base64.b64encode(
            HashUtil.hmac_sha256_encode(k, s).encode(),
        ).decode("utf-8")

    @staticmethod
    def sha1_encode_b64(s: str) -> str:
        """sha1加密，base64编码."""
        return base64.b64encode(HashUtil.sha1_encode(s).encode()).decode(
            "utf-8",
        )


class SignAuth:
    """内部签名工具."""

    def __init__(self, private_key: str) -> None:
        self.private_key = private_key

    def gen_data_str(self, data: dict) -> str:
        params_str = ""
        if not data:
            return params_str
        if not isinstance(data, dict):
            raise TypeError("dict required")
        # for k in sorted(data.keys()):
        #     params_str += str(k)+ str(data[k])
        params_str = orjson.dumps(data, option=orjson.OPT_SORT_KEYS).decode()
        params_str += self.private_key
        return params_str

    def verify(
        self,
        sign: str,
        data: dict,
    ) -> bool:
        """校验sign."""
        sign_tmp = self.generate_sign(data)
        return sign == sign_tmp

    def generate_sign(self, data: dict) -> str:
        """生成sign."""
        data_str = self.gen_data_str(data)
        return HashUtilB64.hmac_sha256_encode_b64(self.private_key, data_str)


class PasswordUtil:
    """密码工具."""

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    @classmethod
    def verify_password(
        cls,
        plain_password: str,
        hashed_password: str,
    ) -> bool:
        return cls.pwd_context.verify(plain_password, hashed_password)  # type: ignore

    @classmethod
    def get_password_hash(cls, plain_password: str) -> str:
        return cls.pwd_context.hash(plain_password)  # type: ignore


T = TypeVar("T", bound=BaseModel)


class JwtUtil(Generic[T]):
    """jwt 工具."""

    default_algorithm = constants.ALGORITHMS.RS256

    def get_jwk_by_kid(kid, jwk_set: dict) -> dict | None:
        for key in jwk_set["keys"]:
            if key["kid"] == kid:
                return key
        return None

    @classmethod
    def decode(
        cls,
        model: type[T],
        token: str | bytes,
        key: str | bytes | Mapping[str, Any],
        algorithms: str = None,
        options: dict | None = None,
        audience: str | None = None,
        issuer: str | None = None,
        subject: str | None = None,
    ) -> T:
        payload = jwt.decode(
            token=token,
            key=key,
            algorithms=algorithms if algorithms else cls.default_algorithm,
            options=options,
            audience=audience,
            issuer=issuer,
            subject=subject,
        )
        return model(**payload)
