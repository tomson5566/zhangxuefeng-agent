"""测试 deepagent_runner 真构造。"""
from backend.modules.deepagent_runner import build_agent_direct, build_agent


def test_build_agent_direct_returns_compiled_graph():
    """不调 LLM,只看 deepagents 能不能造出来。"""
    agent = build_agent_direct(
        api_key='sk-placeholder',
        base_url='https://api.minimaxi.com/v1',
        model='MiniMax-M3',
    )
    assert agent is not None
    assert hasattr(agent, 'astream_events')
    assert hasattr(agent, 'invoke')


def test_build_agent_default_skill():
    """默认 skill_name = 'zhangxuefeng-perspective'"""
    da = build_agent()
    assert da.name == 'deepagent'
    assert da.skill_name == 'zhangxuefeng-perspective'
