"""文档上传模块 — 支持 txt/md/docx/xlsx/pdf/pptx。

公开 API:
- load_file(path)        # 同步解析本地文件
- save_upload(bytes, fn, sid)  # 异步保存上传文件
- list_uploaded(sid)     # 列某 session 已上传文件
- ALLOWED_EXT            # 支持的扩展名集合
"""
from backend.modules.doc_loader.loader import (
    ALLOWED_EXT,
    SUPPORTED_EXTENSIONS,
    list_supported_extensions,
    list_uploaded,
    load_file,
    save_upload,
)

__all__ = [
    "ALLOWED_EXT",
    "SUPPORTED_EXTENSIONS",
    "list_supported_extensions",
    "list_uploaded",
    "load_file",
    "save_upload",
]
