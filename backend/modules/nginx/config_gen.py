"""Nginx 配置生成器 — 自动产出反向代理 + 静态文件 + SSE 长连接配置。

设计:
- generate_nginx_config() 返字符串(配置内容)
- render_to_file(path) 直接写文件(给脚本调用)
- 不在这里跑 nginx 进程(那是运维的活)
- 默认监听 3000,反代 8000(SSE 流式要关 buffer / 加 chunked)
"""
from __future__ import annotations
from pathlib import Path

DEFAULT_PORT = 3000
BACKEND_PORT = 8000


def generate_nginx_config(
    *,
    listen_port: int = DEFAULT_PORT,
    backend_port: int = BACKEND_PORT,
    static_root: str = "../frontend",
) -> str:
    """生成 nginx server block 配置(纯字符串,不写文件)。"""
    return f"""server {{
    listen {listen_port};
    server_name _;

    # 前端静态文件
    root {static_root};
    index index.html;

    # SSE 流式关键:关 buffer,加 chunked transfer
    location /api/chat {{
        proxy_pass http://127.0.0.1:{backend_port};
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;
        chunked_transfer_encoding on;
    }}

    # 其他 API 转发
    location /api/ {{
        proxy_pass http://127.0.0.1:{backend_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}

    # 健康检查
    location /health {{
        proxy_pass http://127.0.0.1:{backend_port};
    }}

    # 文档上传(限制大小)
    location /api/upload {{
        proxy_pass http://127.0.0.1:{backend_port};
        client_max_body_size 50m;
        proxy_set_header Host $host;
    }}

    # 前端 SPA fallback
    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
"""


def render_to_file(path: str | Path, **kwargs) -> None:
    """生成配置并写文件(给 start.sh 调用)"""
    content = generate_nginx_config(**kwargs)
    Path(path).write_text(content, encoding="utf-8")
