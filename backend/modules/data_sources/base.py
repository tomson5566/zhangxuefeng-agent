"""数据源抽象基类 — 各省 loader 继承这个。

设计:
- 统一接口: get_rank_table() / get_school_by_rank() / get_province()
- 适配 dev/prod:基于 __file__ 找 data.json
"""
from __future__ import annotations
import abc
import json
from pathlib import Path
from typing import Any


class DataSource(abc.ABC):
    """数据源基类。"""

    province: str = ""
    year: int = 0
    subject: str = ""

    @abc.abstractmethod
    def get_rank_table(self) -> list[dict[str, Any]]:
        """返回位次段表(7 段左右)"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_school_by_rank(self, rank: int) -> dict[str, Any] | None:
        """按位次找对应段,返 {rank_min, rank_max, score_min, score_max, level, tip, school_examples}"""
        raise NotImplementedError

    def get_province(self) -> str:
        return self.province

    def get_year(self) -> int:
        return self.year

    def get_key_advice(self) -> dict[str, Any]:
        """返回关键建议(red_flag_majors, recommend_majors 等),子类可 override"""
        return {}


class JsonFileDataSource(DataSource):
    """基于本地 data.json 的实现。各省 loader 继承这个 + 设 province/year/subject 即可。

    各 loader 需要在 __init__ 里调 super().__init__ 之前把 self._data_path 设好
    (指向本省 data.json 的绝对路径),否则会用 base.py 所在目录的 data.json。
    """

    _data: dict[str, Any] = None  # 子类延迟加载

    def __init__(self, province: str, year: int, subject: str = "物理类"):
        self.province = province
        self.year = year
        self.subject = subject
        if not hasattr(self, "_data_path") or self._data_path is None:
            # 兜底:用 base.py 同目录(可能不对,但至少不让程序崩)
            self._data_path = Path(__file__).resolve().parent / "data.json"
        self._load()

    def _load(self) -> None:
        if self._data is None:
            self._data = json.loads(self._data_path.read_text(encoding="utf-8"))

    def get_rank_table(self) -> list[dict[str, Any]]:
        return self._data.get("rank_table", [])

    def get_school_by_rank(self, rank: int) -> dict[str, Any] | None:
        """rank 落在哪个段就返哪个段。"""
        for seg in self.get_rank_table():
            if seg["rank_min"] <= rank <= seg["rank_max"]:
                return seg
        # 超出范围 — 返最近的段
        tbl = self.get_rank_table()
        if rank < tbl[0]["rank_min"]:
            return tbl[0]
        return tbl[-1]

    def get_key_advice(self) -> dict[str, Any]:
        return self._data.get("key_advice", {})

    def get_common_misconceptions(self) -> list[dict[str, str]]:
        return self._data.get("common_misconceptions", [])


# 工厂函数:按省名取 loader
def make_loader(province: str) -> DataSource | None:
    """按省名返回对应 loader。province 不区分大小写。"""
    province = province.strip()
    mapping = {
        "福建": "fujian", "fujian": "fujian",
        "北京": "beijing", "beijing": "beijing",
        "广东": "guangdong", "guangdong": "guangdong",
    }
    sub = mapping.get(province)
    if not sub:
        return None
    import importlib
    mod = importlib.import_module(f"backend.modules.data_sources.{sub}.loader")
    # loader.py 里要暴露 `Loader` 类
    return mod.Loader()