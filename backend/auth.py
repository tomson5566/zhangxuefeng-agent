# PUBLIC_FIX_v1
"""最小鉴权:从 nginx auth_basic 注入的 X-Remote-User header 读用户名。

设计:
- /health 不走鉴权
- nginx `proxy_set_header X-Remote-User $remote_user;` 在 auth_basic 成功后注入
- 缺 header / 不匹配白名单 -> 401(不再发 WWW-Authenticate,避免跟 nginx 的 Basic realm 冲突)
- 启动时从 env AUTH_USER 读;空 = 关闭鉴权(向后兼容)
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from backend.config import settings


async def require_auth(
    x_remote_user: str | None = Header(None, alias="X-Remote-User"),
) -> None:
    """FastAPI dependency:校验 nginx auth_basic 注入的 X-Remote-User。"""
    # 鉴权关闭(向后兼容):env 没设 AUTH_USER
    if not settings.auth_user:
        return

    # nginx 没注入(说明 auth_basic 没启用或失败)
    if not x_remote_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Remote-User header missing (nginx auth_basic required)",
            # 注意:不再发 WWW-Authenticate,避免跟 nginx 的 Basic realm 冲突
        )

    # 用户名跟白名单比(当前 settings.auth_user 是单值,简单相等)
    if x_remote_user != settings.auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user",
        )
