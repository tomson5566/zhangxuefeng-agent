# PowerMem 记忆沉淀报告

📅 2026-06-15 23:22

## 任务
老板: 把所有 memory 沉淀到 PowerMem 数据库,10 个维度更新好,不能留空。

## 执行结果

| 项 | 值 |
|---|---|
| 源文件 | 6 个(MEMORY.md + 5 个 daily note) |
| 源文件总行数 | 1356 行 |
| 拆分条数 | **85 条** |
| 写入成功 | **85/85** ✅ 0 失败 |
| 写入耗时 | ~6.5 分钟(平均 4.6 秒/条) |
| 数据库总条数 | 88(3 旧 + 85 新) |
| 10 标签空值数 | **0** ✅ |

## 拆分策略

| 文件 | 拆出条数 | 拆分原则 |
|---|---|---|
| `MEMORY.md`(590 行) | 54 | 按"##" / "###" 小节 1:1 拆分 |
| `memory/2026-06-15.md`(488 行) | 16 | 按反思节 + 当天操作总结 |
| `memory/2026-06-13.md`(87 行) | 3 | 安全测试 3 大主题 |
| `memory/2026-06-11.md`(94 行) | 7 | LangGraph + 反思 + 任务交付 |
| `memory/2026-06-10-续.md`(44 行) | 3 | ask.py 实现细节 |
| `memory/2026-06-10.md`(53 行) | 4 | DeepWiki-Open + 复盘 |

## 10 标签覆盖
每条都含完整 10 标签(无空值),示例:
```json
{
  "tag1_time": "2026-06-15",
  "tag2_topicA": "Python",
  "tag3_topicB": "输出缓冲",
  "tag4_keywordA": "flush",
  "tag5_keywordB": "PYTHONUNBUFFERED",
  "tag6_keywordC": "行缓冲",
  "tag7_project": "coding-agent",
  "tag8_action": "反思",
  "tag9_status": "成功",
  "tag10_priority": "P1"
}
```

## 验证

| 项 | 命令 | 结果 |
|---|---|---|
| 总条数 | `pmem stats` | 88(2 旧 + 1 测试 + 85 新)✅ |
| 写入日志 | `/tmp/pmem_batch.log` | 85 条 OK ✅ |
| 抽检 1 条 10 标签 | `pmem memory get <id>` | 完整 ✅ |
| 语义搜索"zhangxuefeng-agent 鉴权" | `pmem memory search` | 3 条命中(score 0.42-0.56)✅ |
| 语义搜索"CentOS 7 部署 Python" | 同上 | 命中 deep-wiki 部署链路等 3 条(score 0.53-0.58)✅ |
| 语义搜索"派活给 opencode 卡住" | 同上 | 命中 opencode 文档/派活模板/permission 共 3 条(score 0.62-0.68)✅ |

## 沉淀主题分布

按 tag2_topicA 分布:
- **deep-wiki**: ~20 条(技能 / ask.sh / diagram.sh / RAG)
- **shell tool**: ~10 条(沙箱 / 后台 / 缓冲)
- **派活**: ~10 条(opencode / qwen_code / 踩坑)
- **LangGraph**: ~6 条(源码学习 / 设计)
- **zhangxuefeng-agent**: ~6 条(安全 / 鉴权 / 重写)
- **PaddleOCR**: ~3 条(v3 失败 / v2.7 端到端)
- **RAG 架构**: ~3 条(embedding vs 向量库)
- **文档维护**: ~4 条(README / DEPLOY / MEMORY)
- **第三方库 / 下载 / Python**: ~6 条
- **MEMORY 维护 / 反思**: ~17 条

## 决策记录

- **不直接 dump 整文件**:memory_sync.py 默认 500 字符截断会丢信息,我自己读懂 + 按段落拆 + 逐条写
- **不跑 memory_sync.py**:它默认只扫 MEMORY.md/USER.md 且会自动去重,我的需求是"全量沉淀 6 个文件",所以**手写批量脚本 `/tmp/pmem_batch.sh`**
- **不调 LLM 推理**:加 `--no-infer`,3-6 秒/条(原 35-90 秒/条)
- **10 标签手填**:脚本只兜底"未分类",我手填保证每条都具体
- **幂等**:pmem 1.1.x 智能去重,85 条全新无重复

## 教训沉淀(给未来会话)

- **大批量沉淀用手写脚本,不用 memory_sync.py**:脚本默认只扫 MEMORY.md/USER.md,需要 `--file` 参数,自定义拆分要直接调 `pmem memory add`
- **不依赖文件大小判断条数**:6 个文件 1356 行拆 85 条 ≈ 16 行/条,实际是按"## 标题"算
- **批量写要串行**:并行会触发 deep-wiki 那个"RAG 缓存抢资源"问题(虽然这是 PowerMem,Ollama 抢不到,但还是稳一点)

## 交付清单

- `/tmp/all_mems.json` — 85 条记忆源数据(可重跑)
- `/tmp/pmem_batch.sh` — 批量沉淀脚本
- `/tmp/pmem_batch.log` — 写入日志
- 本报告
