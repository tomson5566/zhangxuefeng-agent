"""Backend 包 — 兼容旧 import 路径 + 暴露新 modules/。"""
# 兼容旧路径(下一阶段会逐个迁)
from backend.modules.llm import get_llm  # noqa: F401
from backend.modules.filter import check_input, llm_judge  # noqa: F401
from backend.modules.mmx_search import search_fresh_data  # noqa: F401
from backend.modules.skill_loader import load_skill_prompt, list_skills  # noqa: F401
from backend.modules.doc_loader import SUPPORTED_EXTENSIONS, load_file  # noqa: F401
from backend.modules.deepagent_runner import build_agent, stream_deep  # noqa: F401




