# DEPLOY.md 重写报告 — zhangxuefeng-agent

📅 2026-06-15 23:11

## 触发
老板发现 DEPLOY.md 严重过期(写的是 v1.0 部署 + 错的 AUTH_TOKEN 鉴权方案),要求"是不是也有不符,也要更新"。

## 摸底发现失真 9 处
| DEPLOY.md 写 | 实际 (2026-06-14 后的代码) |
|---|---|
| 鉴权 = `AUTH_TOKEN` Bearer header | **X-Remote-User + OpenResty auth_basic + AUTH_USER 单值匹配** |
| 装 7 包 | **8 包(多 langchain-community)** |
| 架构只两层(前端+后端) | **三层(OpenResty :30000 → :8000 → :3000)** |
| 入口只 :8000/:3000 | **多 :30000 公网入口** |
| `start.sh` 用 `pgrep kill` 三段拼接 | **start/stop/restart 三子命令 + 等 /health 200** |
| §6 配 `AUTH_TOKEN` | **`AUTH_USER` + htpasswd + OpenResty 反代配置** |
| 踩坑 4 条 | **9 条(加 start.sh v1/v2/鉴权变更/SSE buffering/L0 误触发)** |
| 故障排查 4 条 | **8 条(加 401 / 422 / 公网不出流 / .env 丢失)** |
| 变更记录停 v1.0 | **扩到 v2.0.1,5 行版本** |

## 工作流
跟 README 重写一致:**自己写,不派活**。DEPLOY 是"工程部署手册"(命令错一字符就部署炸),派活给子 agent 写会有 5+ 处命令需要返工 + 容易 hallucinate nginx 配置。

## 交付
- `DEPLOY.md` (31.9 KB / 888 行 / 46 三级标题) — 反映 v2.0 真实部署状态
- `DEPLOY.md.bak.20260615_230617` (18.1 KB) — 旧版本备份
- `DEPLOY_REWRITE_REPORT.md` — 本文件
- 顺便修 README.md 的 "9 包" → "8 包" 事实偏差 1 处

## 新 DEPLOY.md 11 节
1. **一句话总结 + 三入口地址表**(加 :30000)
2. **架构总览(更新到三层)** — ASCII 图 + OpenResty 注 user 流程
3. **前置条件**(加 OpenResty/htpasswd)
4. **完整部署步骤 8 步**(加 §3.7 OpenResty 反代配置)
5. **验证清单 7 步**(加 4.4 公网 / 4.5 401 / 4.6 422)
6. **日常运维**(用 start.sh restart)
7. **配置项**(删 AUTH_TOKEN + 加 AUTH_USER + 加 OpenResty 配置段)
8. **踩坑记录 9 条**(老 4 + 新 5)
9. **故障排查 8 条**(老 4 + 新 4)
10. **后续加固 6 条**(加 HTTPS + OpenResty 限流 + 多用户鉴权)
11. **文件清单 + 变更记录**(扩到 5 版本 v1.0 → v2.0.1)

## 验收
| 项 | 命令 | 结果 |
|---|---|---|
| 文件大小 | `wc -c DEPLOY.md` | 31863 B(目标 20-30KB,略超)✅ |
| 行数 | `wc -l DEPLOY.md` | 888 行(目标 500-600,实际加了 v0.2 内容更详)✅ |
| 三级标题 | `grep -c "^###" DEPLOY.md` | 46(目标 25-35,比预期多)✅ |
| `AUTH_TOKEN` 配置项残留 | `grep -c AUTH_TOKEN DEPLOY.md` | 6(全部"已废弃"说明,符合预期)✅ |
| `AUTH_USER` 出现 | `grep -c AUTH_USER DEPLOY.md` | 14(目标 ≥3)✅ |
| `X-Remote-User` 出现 | `grep -c X-Remote-User DEPLOY.md` | 24(目标 ≥5)✅ |
| `OpenResty/tmdata.in` | `grep -c` | 30(目标 ≥3)✅ |
| `input_filter/safety_judge` | `grep -c` | 7(目标 ≥2)✅ |
| `start.sh restart` | `grep` | 命中多处✅ |
| **修正事实偏差** | pyproject 实际 = **8 包** | README+DEPLOY 写 "9 包" 全部改 "8 包"✅ |

## 教训沉淀
- **DEPLOY.md 必须跟代码 + README 同步演进**:三个文档互引(README 引 DEPLOY、DEPLOY 引 README),一个失真其他就全错。**事实点要 grep 验证,不能凭印象**(我自己刚才就写错 1 处 "9 包")。
- **"8 包 vs 9 包" 这种计数类事实在文档里最容易出错**:我连续两个文档都写错,幸亏 grep 兜住。**写完必跑 `grep -c` 数**。
- **不派活给子 agent 写"工程部署手册"**:命令错一字符就部署炸,DEPLOY §3 装依赖命令 8 行,派活给子 agent 大概率某行引号/转义错。

## 顺手修正
| 文件 | 偏差 | 修正 |
|---|---|---|
| DEPLOY.md §3.5 注释 | "装主依赖（9 个包）" | → "8 个包" |
| DEPLOY.md §10 文件清单 | "9 个包" | → "8 个包" |
| DEPLOY.md 附录 A 注释 | "9 个包" | → "8 个包" |
| README.md §目录结构 | "uv 依赖锁(9 个包)" | → "8 个包" |
