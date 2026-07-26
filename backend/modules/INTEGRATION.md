# 模块化架构 — 集成手册

## 架构图

```
backend/
├── core/                 # 核心抽象(阶段 1)
│   ├── agent_base.py     # AgentBase 抽象类
│   ├── skill_registry.py # SKILL.md 自动发现
│   └── module_loader.py  # 模块自动加载
├── modules/              # 可插拔模块(阶段 2-4)
│   ├── llm/              # LLM 抽象 + MiniMax-OpenAI 兼容实现
│   ├── filter/           # 输入过滤 + LLM 审查
│   ├── mmx_search/       # mmx CLI 联网搜索包装
│   ├── skill_loader/     # SKILL.md → system prompt 注入
│   ├── doc_loader/       # 文档上传 5 格式
│   ├── nginx/            # nginx 反代 + SSE 配置生成
│   └── deepagent_runner/ # deepagents 封装
└── (旧文件保留兼容)
```

## 7 个模块一览

| 模块 | 路径 | 功能 | registry key |
|---|---|---|---|
| llm | modules/llm/ | LLM 工厂(MiniMax 走 OpenAI 兼容) | `llm_factory` |
| filter | modules/filter/ | 输入过滤 + LLM 审查 | `input_filter`, `llm_judge` |
| mmx_search | modules/mmx_search/ | 联网搜索(包装 mmx CLI) | `mmx_search` |
| skill_loader | modules/skill_loader/ | 加载 SKILL.md 注入 prompt | `skill_loader`, `load_skill_prompt`, `list_skills` |
| doc_loader | modules/doc_loader/ | 文档上传 5 格式 | `doc_loader`, `doc_extensions` |
| nginx | modules/nginx/ | 反代 + SSE 配置生成 | `nginx_generator`, `nginx_render_to_file`, `nginx_default_port` |
| deepagent_runner | modules/deepagent_runner/ | deepagents 封装 + 流式接口 | `deepagent_factory`, `deepagent_stream` |

## ModuleRegistry 用法

```python
from backend.core.module_loader import ModuleLoader, default_registry

# 自动加载所有 7 个模块
loaded = ModuleLoader.load_all(default_registry)
# → ['deepagent_runner', 'doc_loader', 'filter', 'llm', 'mmx_search', 'nginx', 'skill_loader']

# 取组件
llm_factory = default_registry.get("llm_factory")
mmx_search = default_registry.get("mmx_search")
deepagent_factory = default_registry.get("deepagent_factory")
```

## 换 skill = 换角色

```python
from backend.modules.deepagent_runner import build_agent

# 加载"张雪峰"角色
da = build_agent(skill_name="zhangxuefeng-perspective")
agent = da._build_internal()

# 加载"老纪技术唠嗑师"角色
da2 = build_agent(skill_name="技术唠嗑师")
agent2 = da2._build_internal()
```

`SkillRegistry.discover()` 自动扫以下路径找 SKILL.md:
- `~/.copaw/workspaces/default/skills/`
- `~/.copaw/workspaces/coding-agent/skills/`
- `<project>/skills/`

## 文档上传

```python
from backend.modules.doc_loader import load_file, SUPPORTED_EXTENSIONS

# 支持的格式
print(SUPPORTED_EXTENSIONS)  # {'.txt', '.md', '.docx', '.xlsx', '.pdf', '.pptx'}

# 加载文件
text = load_file("/path/to/report.pdf")
```

## Nginx 配置生成

```python
from backend.modules.nginx import generate_nginx_config, render_to_file

# 生成配置字符串
config = generate_nginx_config(listen_port=3000, backend_port=8000)

# 直接写文件
render_to_file("/etc/nginx/conf.d/zhangxuefeng.conf", listen_port=3000)
```

## 新增模块流程

1. 在 `backend/modules/<name>/` 下新建 `__init__.py` + 实现代码
2. 写 `register.py`,暴露 `register(registry)` 函数
3. 主程序下次启动自动加载

## 依赖清单(pyproject.toml)

```toml
dependencies = [
    "fastapi>=0.136.3",
    "langchain>=1.3.7",
    "langchain-community>=0.4.2",
    "langchain-core>=1.4.6",
    "langchain-openai>=1.3.0",
    "python-dotenv>=1.2.2",
    "sse-starlette>=3.4.4",
    "uvicorn[standard]>=0.49.0",
    "deepagents>=0.6.12",
    "python-docx>=1.1.0",
    "openpyxl>=3.1.5",
    "pypdf>=5.0.0",
    "python-pptx>=1.0.2",
    "markdown>=3.6",
]
```

## 测试

```bash
# 文档加载 5 格式
.venv/bin/python backend/tests/test_doc_loader.py

# E2E 集成 6 项
.venv/bin/python backend/tests/test_e2e.py
```

## 升级路径

- 阶段 1 ✅ — core 抽象
- 阶段 2 ✅ — 8 个旧 .py 迁到 modules/
- 阶段 3 ✅ — deepagents 接入
- 阶段 4 ✅ — 文档上传 5 格式
- 阶段 5 ✅ — E2E + 集成文档
