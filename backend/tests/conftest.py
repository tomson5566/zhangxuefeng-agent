"""pytest 共享 fixtures。"""
import sys, os, pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SKIP_LIVE = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_TESTS"),
    reason="需要真实 LLM key,设 RUN_LIVE_TESTS=1 才跑",
)
