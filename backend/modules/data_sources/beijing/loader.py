"""北京市数据源"""
from __future__ import annotations
from pathlib import Path
from backend.modules.data_sources.base import JsonFileDataSource


class Loader(JsonFileDataSource):
    def __init__(self):
        self._data_path = Path(__file__).resolve().parent / "data.json"
        super().__init__(province="北京", year=2025, subject="物理类")