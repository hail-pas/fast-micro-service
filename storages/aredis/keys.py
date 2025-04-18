from enum import Enum, unique


@unique
class UserCenterKey(str, Enum):
    AccountApiPermissionSet = "UC:Account:Apis:{uuid}"
    Token2AccountKey = "UC:Token:{token}"  # Authorization 拼接key， 存储的 acount_id:scene
    Account2TokenKey = "UC:Account:{account_id}:{scene}"  # 存储的 token:account_id
    AccountBaseInfo = "UC:Account:BaseInfo:{uuid}"
    CodeUniqueKey = "UC:Code:{scene}:{identifier}"


@unique
class RedisCacheKey(str, Enum):
    ForwardPlatformKey: str = "ForwardPlatform:{platform_id}"  # 转发平台信息 hset
    ForwardConnectionStatus: str = "ForwardConnectionStatus:{platform_id}"  # 转发连接状态
    ForwardDelay: str = "ForwardDelay:{platform_id}:{hour}"  # 每小时转发延迟 hset
    ApiSecretKey: str = "ApiKey:SecretKey:{api_key}"  # ApiKey 密钥
    ApiKeyPermissionSet = "ApiKey:Apis:{api_key}"  # ApiKey接口权限
    WhiteListLocations = "WhiteList:{whitelist_id}"  # 白名单 里面是set 关联的location集合
