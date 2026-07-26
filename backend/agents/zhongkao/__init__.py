"""中考志愿 agent — 福州普高分流建议。"""
from backend.agents.zhongkao.agent import stream_answer, warmup as agent_warmup
from backend.agents.zhongkao.prompt import build_system_prompt, warmup as prompt_warmup

__all__ = ["stream_answer", "build_system_prompt", "agent_warmup", "prompt_warmup"]


def warmup() -> None:
    prompt_warmup()
    agent_warmup()
