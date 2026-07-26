"""E2E:chat 流式(需要真实 LLM,默认 skip)。

跑这个测试: RUN_LIVE_TESTS=1 .venv/bin/python -m pytest backend/tests/e2e/ -v
"""
import os
import pytest


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_TESTS"),
    reason="需要真实 LLM key,设 RUN_LIVE_TESTS=1 才跑"
)
def test_chat_stream_smoke():
    from backend.modules.deepagent_runner import build_agent_direct
    agent = build_agent_direct(
        api_key=os.environ.get('OPENAI_API_KEY', 'sk-placeholder'),
        base_url=os.environ.get('OPENAI_BASE_URL', 'https://api.minimaxi.com/v1'),
        model=os.environ.get('MODEL_NAME', 'MiniMax-M3'),
    )
    assert agent is not None
    # 真流式会真发请求,这里只验证 agent 构造可工作,详细 E2E 需要 key
